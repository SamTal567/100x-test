"""Server-owned learning flow, durable turns, and prepared evidence assessment."""
from __future__ import annotations

from app.services.report_progress import revision_conflicts
import hashlib
import json
import threading
from datetime import datetime, timezone
from sqlalchemy import update
from app.db.models import (Session, Message, Attempt, Gap, CriterionAssessment, CasePrompt,
    Intervention, TurnIdempotency, Attachment, Transcription, Concept)
from app.schemas import TurnRequest, TurnResponse, MessageOut, CasePromptOut, TranscriptionSegment
from app.services.evidence import snapshot_case, assessment_answer, validate_exercise, exercise_results, normalized_proposal
from app.services.reports import attempt_reports, build_report
from app.resources import LESSONS, RESOURCE_VERSION

STAGE_ACTIONS = {
    "diagnostic": ["submit_answer", "clarify", "finish_session", "retry_processing"],
    "investigate": ["submit_answer", "answer_probe", "clarify", "correct_ai", "request_hint",
        "request_teaching", "request_practice", "submit_practice", "request_help", "resource_opened",
        "resource_completed", "continue", "finish_session", "retry_processing"],
    "apply": ["submit_answer", "clarify", "finish_session", "retry_processing"],
    "review": ["retry_processing"], "completed": ["retry_processing"],
}
_RUNNING = set()
_RUNNING_LOCK = threading.Lock()
PRACTICE_TYPES = ("practice", "guided_practice")


class SessionService:
    def __init__(self, db):
        # Keep the public seam used by provider-isolated API tests.
        from app.services.session_service import get_openai_adapter
        self.db, self.ai = db, get_openai_adapter()
        self._attempt = None

    def get_allowed_actions(self, stage):
        return STAGE_ACTIONS.get(stage, [])

    def get_evidence_cards(self, session):
        return [{"id": g.id, "gap_description": g.description, "evidence_quote": g.evidence_quote,
            "probe_question": g.probe_text, "source_attempt_id": g.source_attempt_id, "status": g.status}
            for g in self.db.query(Gap).filter_by(session_id=session.id).order_by(Gap.created_at)]

    def get_attempt_reports(self, session):
        return attempt_reports(self.db, session)

    def generate_report(self, session):
        return build_report(self.db, session)

    def _message(self, session, messages, content, provider_status="complete", role="tutor"):
        msg = Message(session_id=session.id, role=role, content=content, stage=session.stage, provider_status=provider_status)
        self.db.add(msg)
        self.db.flush()
        messages.append(msg)
        return msg

    def _response(self, session, messages=(), status="complete", intervention=None):
        case = self.db.get(CasePrompt, session.current_prompt_id) if session.current_prompt_id else None
        return TurnResponse(stage=session.stage, version=session.version,
            diagnostic_index=session.diagnostic_index, diagnostic_total=len(session.baseline_prompt_ids or []), messages=[MessageOut.model_validate(m) for m in messages],
            current_prompt=CasePromptOut.model_validate(case) if case else None,
            allowed_actions=self.get_allowed_actions(session.stage), processing_status=status,
            evidence_cards=self.get_evidence_cards(session), intervention=intervention,
            practice_active=bool(case and case.case_type in PRACTICE_TYPES and session.stage == "investigate"))

    def _baseline_cases(self, session):
        if not session.baseline_prompt_ids:
            session.baseline_prompt_ids = [c.id for c in self.db.query(CasePrompt).filter_by(
                concept_id=session.concept_id, stage="diagnostic", active=True).order_by(CasePrompt.sort_order, CasePrompt.id)]
        return [self.db.get(CasePrompt, key) for key in session.baseline_prompt_ids]

    def _gap(self, session):
        return self.db.query(Gap).filter_by(session_id=session.id).order_by(Gap.created_at).first()

    def _source_case(self, session):
        gap = self._gap(session)
        source = self.db.get(Attempt, gap.source_attempt_id) if gap else None
        return source.case_prompt if source else self.db.get(CasePrompt, session.current_prompt_id)

    def _validate(self, session, turn, owner_id):
        if session.owner_id != owner_id:
            raise ValueError("Session owner does not match")
        if turn.action not in self.get_allowed_actions(session.stage):
            raise ValueError(f"Action '{turn.action}' not allowed in stage '{session.stage}'")
        if turn.prompt_id is not None and turn.prompt_id != session.current_prompt_id:
            raise ValueError("Submitted prompt does not match the current prompt")
        case = self.db.get(CasePrompt, session.current_prompt_id) if session.current_prompt_id else None
        if turn.action in ("submit_answer", "submit_practice"):
            if not case:
                raise ValueError("No current prompt is available")
            if not turn.text or not turn.text.strip():
                raise ValueError("Please explain your reasoning as well as selecting exercise answers")
            practice = case.case_type in PRACTICE_TYPES and session.stage == "investigate"
            if practice != (turn.action == "submit_practice"):
                raise ValueError("Use submit_practice for the active practice prompt before revising the original answer")
            validate_exercise(case, turn)
        if turn.action in ("answer_probe", "correct_ai") and not (turn.text or "").strip():
            raise ValueError("Write a message before sending")
        for key in turn.attachment_ids:
            record = self.db.get(Attachment, key)
            if not record or record.owner_id != owner_id or record.session_id != session.id:
                raise ValueError("Attachment does not belong to this session")
        voice_segments = self._voice_segments(turn)
        for segment in voice_segments:
            record = self.db.get(Transcription, segment.transcription_id)
            if not record or record.owner_id != owner_id or record.session_id != session.id:
                raise ValueError("Transcription does not belong to this session")
            if record.status not in ("transcribed", "confirmed"):
                raise ValueError("Transcription is not ready to confirm")
            if turn.input_mode != "voice" or not (turn.text or "").strip():
                raise ValueError("Confirm the edited voice transcript before submission")
        if turn.input_mode == "voice" and not voice_segments:
            raise ValueError("Voice input must reference the reviewed transcription")
        if turn.action in ("resource_opened", "resource_completed"):
            item = self.db.get(Intervention, turn.resource_id) if turn.resource_id else None
            if turn.resource_id or turn.action == "resource_completed":
                if not item or item.session_id != session.id or item.intervention_type != "resource":
                    raise ValueError("Resource event must identify a resource from this session")
                if turn.text and turn.text != item.url:
                    raise ValueError("The guide URL does not match this resource")
            else:
                concept = self.db.get(Concept, session.concept_id)
                if not concept or concept.slug not in LESSONS or turn.text not in (None, "", f"/v1/resources/{concept.slug}"):
                    raise ValueError("Only the current concept's prepared guide can be opened without a resource ID")

    @staticmethod
    def _voice_segments(turn):
        if turn.transcription_segments:
            return turn.transcription_segments
        if turn.transcription_id:
            return [TranscriptionSegment(transcription_id=turn.transcription_id,
                confirmed_text=turn.text or "", confirmation_scope="legacy_draft")]
        return []

    def _confirm_transcripts(self, turn, message, attempt):
        segments = self._voice_segments(turn)
        ids = [segment.transcription_id for segment in segments]
        for segment in segments:
            record = self.db.get(Transcription, segment.transcription_id)
            event = {"edited": segment.confirmed_text != record.raw_transcript,
                "confirmed_text": segment.confirmed_text, "confirmed_at": datetime.now(timezone.utc).isoformat(),
                "confirmation_scope": segment.confirmation_scope, "transcription_ids": ids,
                "message_id": message.id if message else None, "attempt_id": attempt.id if attempt else None}
            metadata = dict(record.correction_metadata or {})
            prior = list(metadata.get("confirmations", []))
            if record.confirmed_text is not None and not prior:
                prior.append({"confirmed_text": record.confirmed_text, "confirmation_scope": "historical_unknown", **metadata})
            metadata.update({key: value for key, value in event.items() if key != "confirmed_text"})
            metadata["confirmations"] = prior + [event]
            record.confirmed_text, record.status = segment.confirmed_text, "confirmed"
            record.correction_metadata = metadata

    def _support(self, session, stage):
        if stage in ("diagnostic", "apply"):
            return "independent"
        interventions = self.db.query(Intervention).filter_by(session_id=session.id).all()
        types = {i.intervention_type for i in interventions if i.status == "delivered"}
        if any(i.intervention_type == "resource" and (i.opened_at or i.completed_at) for i in interventions):
            types.add("resource_used")
        if any(i.intervention_type == "resource" for i in interventions):
            types.add("resource")
        for kind, label in [("teaching", "after_teaching"), ("tutoring_unknown", "after_help_unknown"), ("hint", "after_hint"),
                            ("practice", "after_practice"), ("resource_used", "after_resource"), ("resource", "after_help_offered"),
                            ("clarification", "after_clarification")]:
            if kind in types:
                return label
        return "after_follow_up"

    def _new_attempt(self, session, turn, case):
        stage = "practice" if turn.action == "submit_practice" else session.stage
        gap = self._gap(session) if stage in ("investigate", "practice", "apply") else None
        attempt = Attempt(session_id=session.id, case_prompt_id=case.id, stage=stage,
            answer_text=turn.text.strip(), input_mode=turn.input_mode, diagram_state=turn.diagram_state,
            cloze_state=turn.cloze_state, rubric_version=case.rubric.version if case.rubric else None,
            gap_id=gap.id if gap else None, case_snapshot=snapshot_case(case),
            support_level=self._support(session, stage), processing_status="pending")
        segments = self._voice_segments(turn)
        if segments:
            attempt.raw_transcript = "\n\n".join(self.db.get(Transcription, segment.transcription_id).raw_transcript or "" for segment in segments)
        self.db.add(attempt)
        self.db.flush()
        return attempt

    async def process_turn(self, session, turn: TurnRequest, owner_id):
        if session.owner_id != owner_id:
            raise ValueError("Session owner does not match")
        key = hashlib.sha256(f"{session.id}:{turn.client_turn_id}".encode()).hexdigest()
        body = turn.model_dump(mode="json")
        if not body.get("transcription_segments"):
            body.pop("transcription_segments", None)  # Keep pre-upgrade saved request hashes valid.
        digest = hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()
        existing = self.db.get(TurnIdempotency, key)
        if existing and existing.request_body_hash != digest:
            raise ValueError("Conflicting turn payload for client_turn_id")
        if existing and existing.state == "complete" and existing.response_snapshot:
            return TurnResponse.model_validate(existing.response_snapshot)
        with _RUNNING_LOCK:
            if key in _RUNNING:
                self.db.refresh(session)
                return self._response(session, status="processing")
            _RUNNING.add(key)
        messages, intervention = [], None
        try:
            if not existing:
                self._validate(session, turn, owner_id)
                reservable = Session.processing_turn_id.is_(None)
                abandoned = None
                if turn.action == "finish_session" and session.processing_status == "failed":
                    abandoned = self.db.get(TurnIdempotency, session.processing_turn_id)
                    reservable = (Session.processing_status == "failed")
                result = self.db.execute(update(Session).where(Session.id == session.id,
                    Session.owner_id == owner_id, Session.version == turn.expected_version,
                    reservable).values(version=Session.version + 1,
                    processing_turn_id=key, processing_status="processing"), execution_options={"synchronize_session": False})
                if result.rowcount != 1:
                    self.db.rollback()
                    raise ValueError("Version mismatch or another turn is still processing; reload or retry the saved turn")
                self.db.refresh(session)
                if abandoned:
                    abandoned.state = "abandoned"
                self._baseline_cases(session)
                existing = TurnIdempotency(client_turn_id=key, session_id=session.id,
                    request_body_hash=digest, request_payload=body, state="processing")
                self.db.add(existing)
                learner = None
                self._attempt = None
                if turn.text:
                    learner = self._message(session, messages, turn.text, role="learner")
                    segments = self._voice_segments(turn)
                    learner.input_mode = turn.input_mode
                    learner.transcription_id = segments[-1].transcription_id if segments else None
                    learner.attachment_ids = turn.attachment_ids
                if turn.action in ("submit_answer", "submit_practice"):
                    self._attempt = self._new_attempt(session, turn, self.db.get(CasePrompt, session.current_prompt_id))
                    existing.attempt_id = self._attempt.id
                self._confirm_transcripts(turn, learner, self._attempt)
                self.db.commit()  # Durable checkpoint BEFORE external calls.
            else:
                self.db.refresh(session)
                if session.owner_id != owner_id or session.processing_turn_id != key:
                    raise ValueError("This interrupted turn cannot be resumed after a different turn")
                self._attempt = self.db.get(Attempt, existing.attempt_id) if existing.attempt_id else None
                existing.state, session.processing_status = "processing", "processing"
                self.db.commit()
            if turn.action == "finish_session":
                session.stage = "completed"
                self._message(session, messages, "Session finished with the evidence collected so far. Unanswered or unassessed areas remain inconclusive.")
            elif turn.action == "retry_processing":
                await self._retry_assessment(session, messages)
            elif turn.action == "clarify":
                await self._clarify(session, turn, messages)
            elif session.stage == "diagnostic":
                session.diagnostic_index = self.db.query(Attempt).filter_by(session_id=session.id, stage="diagnostic").count()
                cases = self._baseline_cases(session)
                if session.diagnostic_index < len(cases):
                    self._attempt.processing_status = "complete"
                    session.current_prompt_id = cases[session.diagnostic_index].id
                    self._message(session, messages, "Answer saved. Here is the next independent scenario.")
                else:
                    await self._baseline(session, messages)
            elif session.stage == "investigate":
                if turn.action == "submit_answer":
                    await self._assess_attempt(self._attempt)
                    original = self.db.get(Attempt, self._gap(session).source_attempt_id) if self._gap(session) else None
                    conflicts = self._revision_conflicts(original, self._attempt)
                    if conflicts:
                        criterion = conflicts[0]['criterion']
                        self._message(session, messages, f"Your revision is saved, but its assessment is inconsistent with your earlier reasoning about '{criterion}'. "
                            "This may be an interpretation or assessment issue, not a confirmed misconception. "
                            "Could you clarify what you intended in the revised answer? You can return to chat, revise again, or choose to proceed to the unfamiliar case.")
                    else:
                        self._to_apply(session, messages)
                elif turn.action == "submit_practice":
                    await self._assess_attempt(self._attempt)
                    source = self._source_case(session)
                    session.current_prompt_id = source.id
                    self._message(session, messages, "Practice saved. Review its criterion feedback below. Keep chatting, try another practice, or submit your revised explanation.")
                elif turn.action == "request_practice":
                    self._practice(session, messages)
                elif turn.action == "continue":
                    self._to_apply(session, messages)
                elif turn.action == "request_help":
                    intervention = self._resource(session, messages)
                elif turn.action in ("resource_opened", "resource_completed"):
                    item = self.db.get(Intervention, turn.resource_id) if turn.resource_id else self._resource(session, messages, offer_message=False)
                    if turn.action == "resource_opened":
                        self._snapshot_opened_guide(item)
                    field = "opened_at" if turn.action == "resource_opened" else "completed_at"
                    if getattr(item, field) is None:
                        setattr(item, field, datetime.now(timezone.utc))
                    intervention = {"id": item.id, "type": "resource", "title": item.title, "url": item.url, "content": item.content}
                else:
                    await self._tutor(session, turn, messages)
            elif session.stage == "apply" and turn.action == "submit_answer":
                await self._assess_attempt(self._attempt)
                session.stage = "completed"
                self._message(session, messages, "Your unfamiliar-case answer is saved. The evidence report compares your reasoning and records help used. AI judgments remain provisional.")
            self.db.flush()
            session.processing_status, session.processing_turn_id = "complete", None
            response = self._response(session, messages, intervention=intervention)
            existing.state, existing.response_snapshot = "complete", response.model_dump(mode="json")
            self.db.commit()
            return response
        except BaseException:
            self.db.rollback()
            record = self.db.get(TurnIdempotency, key)
            if record and record.state != "complete":
                record.state = "failed"
                self.db.get(Session, session.id).processing_status = "failed"
                self.db.commit()
            raise
        finally:
            with _RUNNING_LOCK:
                _RUNNING.discard(key)

    async def _assess_attempt(self, attempt, case=None, rubric=None, unavailable_reason=""):
        snapshot = attempt.case_snapshot or snapshot_case(case or attempt.case_prompt)
        prepared, answer = snapshot.get("rubric", {}), assessment_answer(attempt)
        self.db.commit()  # No write transaction while awaiting the provider.
        result = await self.ai.assess_attempt(
            scenario=snapshot["scenario_text"],
            answer=answer,
            reference_answer=prepared.get("reference_answer", ""),
            criteria=prepared.get("criteria", []),
            question_parts=snapshot.get("question_parts"),
        )
        attempt.question_parts_coverage = [
            p.model_dump() if hasattr(p, "model_dump") else p
            for p in result.question_parts_coverage
        ] if getattr(result, "question_parts_coverage", None) else None
        reviewed = {c.criterion for c in attempt.criterion_assessments if c.status in ("reviewed", "corrected")}
        self.db.query(CriterionAssessment).filter_by(attempt_id=attempt.id, status="provisional").delete(synchronize_session=False)
        for criterion in prepared.get("criteria", []):
            if criterion["criterion"] in reviewed:
                continue
            matches = [c for c in result.criteria if c.criterion == criterion["criterion"]]
            proposal = normalized_proposal(
                matches[0] if len(matches) == 1 else None,
                answer,
                result.status,
                result.summary,
                question_parts=snapshot.get("question_parts"),
                criterion_id=criterion.get("criterion"),
            )
            met, rating, evidence = proposal
            self.db.add(CriterionAssessment(
                attempt_id=attempt.id,
                criterion=criterion["criterion"],
                skill_id=criterion.get("skill_id"),
                met=met,
                rating=rating,
                evidence=evidence,
                status="provisional",
                question_part_id=proposal.question_part_id,
                coverage=proposal.coverage,
                issue_type=proposal.issue_type,
                demonstrated_explanation=proposal.demonstrated_explanation,
                explanation=proposal.explanation,
                next_action=proposal.next_action,
            ))
        for objective in exercise_results(snapshot, attempt.diagram_state, attempt.cloze_state):
            if objective["criterion"] in reviewed:
                continue
            self.db.add(CriterionAssessment(attempt_id=attempt.id, status="provisional", **objective))
        attempt.processing_status = "complete"
        self.db.flush()
        self.db.expire(attempt, ["criterion_assessments"])

    async def _baseline(self, session, messages):
        attempts = self.db.query(Attempt).filter_by(session_id=session.id, stage="diagnostic").order_by(Attempt.created_at).all()
        complete = True
        for attempt in attempts:
            snapshot = attempt.case_snapshot or snapshot_case(attempt.case_prompt)
            prepared = snapshot["rubric"]
            case_name = (
                snapshot.get("title")
                or (snapshot.get("diagram_preset") or {}).get("title")
                or (snapshot.get("cloze_preset") or {}).get("title")
                or (snapshot.get("scenario_text", "").strip().split("\n")[0][:60].strip())
                or "the scenario"
            )
            if not attempt.criterion_assessments:
                await self._assess_attempt(attempt)
            self.db.commit()
            analysis = await self.ai.analyse_answer(scenario=snapshot["scenario_text"], answer=attempt.answer_text,
                reference_answer=prepared.get("reference_answer", ""), criteria=prepared.get("criteria", []))
            complete = complete and analysis.status == "complete"
            quote = analysis.evidence_quote or ""
            if (analysis.status == "complete" and analysis.gap_found and quote.strip()
                and quote.casefold() in attempt.answer_text.casefold() and not self._gap(session)):
                self.db.add(Gap(session_id=session.id, source_attempt_id=attempt.id, description=analysis.description,
                    evidence_quote=quote, probe_text=analysis.probe_question or f"In {case_name}: Which stated facts support your explanation, and what would break if your assumption changed?", status="identified"))
                self.db.flush()
            if not self._gap(session):
                uncertain = next((c for c in attempt.criterion_assessments
                    if not (c.skill_id or "").startswith("exercise:")
                    and c.rating in ("not_addressed", "ambiguous_needs_clarification", "partially_demonstrated")), None)
                if uncertain:
                    criterion = next((c for c in prepared.get("criteria", []) if c["criterion"] == uncertain.criterion), {})
                    probes = criterion.get("follow_up_probes") or []
                    if uncertain.issue_type == "missing_requested_part" or uncertain.rating == "not_addressed":
                        exp = uncertain.explanation or f"You did not address {uncertain.criterion}."
                        probe = f"In {case_name}: {exp} How would you answer this part?"
                    elif uncertain.issue_type in ("ambiguous_wording_or_interpretation", "ambiguous_wording", "insufficient_evidence") or uncertain.rating == "ambiguous_needs_clarification":
                        probe = f"In {case_name}: Your explanation about {uncertain.criterion} was ambiguous. What did you mean?"
                    elif uncertain.issue_type == "incorrect_claim" or uncertain.rating == "partially_demonstrated":
                        claim = uncertain.evidence or uncertain.criterion
                        probe = f"In {case_name}: Could you explain the reasoning behind: '{claim}'? What happens if that assumption is tested?"
                    elif probes:
                        probe = probes[0]
                    else:
                        probe = f"In {case_name}: Could you explain your reasoning about this part: {uncertain.criterion}? State any assumptions you used."

                    evidence = uncertain.evidence if uncertain.evidence and uncertain.evidence.casefold() in attempt.answer_text.casefold() else None
                    if uncertain.rating == "not_addressed" or uncertain.issue_type == "missing_requested_part":
                        evidence = None
                    self.db.add(Gap(session_id=session.id, source_attempt_id=attempt.id,
                        description=f"Needs clarification: {uncertain.criterion}. This may be an omission or interpretation issue; no misconception is confirmed.",
                        evidence_quote=evidence, probe_text=probe, status="needs_clarification"))
                    self.db.flush()
            self.db.commit()
        session.baseline_analysis_status = "complete" if complete else "error"
        gap = self._gap(session)
        if gap:
            session.stage = "investigate"
            session.current_prompt_id = self.db.get(Attempt, gap.source_attempt_id).case_prompt_id
            self._message(session, messages, gap.probe_text)
        else:
            self._to_apply(session, messages, confirmation=True)
            if not complete:
                self._message(session, messages, "Gap analysis was unavailable or uncertain. Criterion assessments were attempted separately; no weakness or mastery is inferred from that failure.", provider_status="error")

    async def _retry_assessment(self, session, messages):
        attempts = self.db.query(Attempt).filter_by(session_id=session.id).order_by(Attempt.created_at).all()
        count = 0
        for attempt in attempts:
            if not attempt.case_snapshot:
                continue  # Legacy wording/key cannot be reconstructed truthfully.
            if not attempt.criterion_assessments or any(c.rating == "technical_failure" for c in attempt.criterion_assessments):
                await self._assess_attempt(attempt)
                count += 1
        baseline = [a for a in attempts if a.stage == "diagnostic"]
        if baseline and session.baseline_analysis_status != "complete" and len(baseline) == len(session.baseline_prompt_ids or []):
            complete = True
            for attempt in baseline:
                snapshot = attempt.case_snapshot
                if not snapshot:
                    complete = False
                    continue
                self.db.commit()
                analysis = await self.ai.analyse_answer(scenario=snapshot["scenario_text"], answer=attempt.answer_text,
                    reference_answer=snapshot["rubric"]["reference_answer"], criteria=snapshot["rubric"]["criteria"])
                complete = complete and analysis.status == "complete"
                if (analysis.status == "complete" and analysis.gap_found and analysis.evidence_quote.strip()
                    and analysis.evidence_quote.casefold() in attempt.answer_text.casefold() and not self._gap(session)):
                    self.db.add(Gap(session_id=session.id, source_attempt_id=attempt.id, description=analysis.description,
                        evidence_quote=analysis.evidence_quote, probe_text=analysis.probe_question, status="identified"))
                    self.db.flush()
            session.baseline_analysis_status = "complete" if complete else "error"
        self._message(session, messages, f"Retried assessment of {count} saved answer(s). No new learner attempt was created and human reviews were preserved. Any unavailable judgments remain inconclusive.")

    def _choose_apply(self, session, confirmation=False):
        seen_ids = {a.case_prompt_id for a in self.db.query(Attempt).join(Session).filter(Session.owner_id == session.owner_id)}
        seen_ids.update(s.current_prompt_id for s in self.db.query(Session).filter_by(owner_id=session.owner_id) if s.current_prompt_id)
        seen_authored = {c.authored_id for c in self.db.query(CasePrompt).filter(CasePrompt.id.in_(seen_ids)) if c.authored_id}
        candidates = self.db.query(CasePrompt).filter_by(concept_id=session.concept_id, stage="apply", active=True).order_by(CasePrompt.sort_order, CasePrompt.id).all()
        candidates = [c for c in candidates if c.id not in seen_ids and (not c.authored_id or c.authored_id not in seen_authored)]
        source = self._source_case(session)
        source_skills = {c.get("skill_id") for c in source.rubric.criteria} if source and source.rubric else set()
        def score(case):
            overlap = len(source_skills & {c.get("skill_id") for c in case.rubric.criteria}) if case.rubric else 0
            return (case.case_type == ("confirmation" if confirmation else "transfer"), overlap)
        candidates.sort(key=score, reverse=True)
        return candidates[0] if candidates and (not source_skills or score(candidates[0])[1]) else None

    def _to_apply(self, session, messages, confirmation=False):
        case = self._choose_apply(session, confirmation)
        if not case:
            session.stage = "completed"
            self._message(session, messages, "No unused authored scenario is available for this concept. Your evidence is saved; unfamiliar-case application remains unassessed.")
            return
        session.stage, session.current_prompt_id = "apply", case.id
        facts = "\n".join(f"- {a}" for a in (case.assumptions or []))
        scenario_msg = (
            f"Here is your unfamiliar scenario to test your understanding:\n\n"
            f"> {case.scenario_text}"
            + (f"\n\n**Stated assumptions:**\n{facts}" if facts else "")
            + "\n\nExplain what happens in this unfamiliar case and why. The report will show which prepared criteria your answer demonstrates, separately from your baseline and any supported revision."
        )
        self._message(session, messages, scenario_msg)

    async def _clarify(self, session, turn, messages):
        case = self.db.get(CasePrompt, session.current_prompt_id)
        # Only prior clarification turns for this exact prompt, never general
        # tutoring, reference answers, private presets or a different case.
        recent = self.db.query(TurnIdempotency).filter_by(session_id=session.id, state="complete").order_by(
            TurnIdempotency.created_at.desc(), TurnIdempotency.client_turn_id.desc()).limit(40).all()
        history = []
        matching = [item for item in reversed(recent) if (item.request_payload or {}).get("action") == "clarify"
            and (item.request_payload or {}).get("prompt_id") == case.id]
        for item in matching[-4:]:
            history.append({"role": "learner", "content": ((item.request_payload or {}).get("text") or "")[-2000:]})
            for message in (item.response_snapshot or {}).get("messages", []):
                if message.get("role") == "tutor" and message.get("provider_status", "complete") == "complete":
                    history.append({"role": "tutor", "content": message.get("content", "")[-2000:]})
        public_scenario, assumptions = case.scenario_text, list(case.assumptions or [])
        self.db.commit()  # The question is already saved; release DB work before AI.
        reply = await self.ai.clarify_scenario(scenario=public_scenario, assumptions=assumptions,
            question=turn.text or "Please explain what this question is asking me to do.",
            stage=session.stage, history=history)
        self._message(session, messages, reply.message, reply.status)
        self._intervention(session, "clarification", "AI scenario clarification", reply.message,
            "delivered" if reply.status == "complete" else reply.status)

    def _intervention(self, session, kind, title, content, status="delivered", url=None):
        gap = self._gap(session)
        item = Intervention(session_id=session.id, gap_id=gap.id if gap else None,
            intervention_type=kind, title=title, content=content, status=status, url=url)
        self.db.add(item)
        self.db.flush()
        return item

    @staticmethod
    def _revision_conflicts(original, revised):
        if not original or not revised or not original.case_snapshot or not revised.case_snapshot:
            return []
        if original.case_prompt_id != revised.case_prompt_id or original.rubric_version != revised.rubric_version:
            return []
        if original.case_snapshot.get('version') != revised.case_snapshot.get('version'):
            return []
        fields = ('criterion', 'skill_id', 'rating', 'met', 'issue_type', 'evidence')
        return revision_conflicts([{k: getattr(c, k) for k in fields} for c in original.criterion_assessments],
                                  [{k: getattr(c, k) for k in fields} for c in revised.criterion_assessments])

    async def _tutor(self, session, turn, messages):
        gap, case = self._gap(session), self.db.get(CasePrompt, session.current_prompt_id)
        original = self.db.get(Attempt, gap.source_attempt_id) if gap else None
        # Use the wording/key actually attached to this answer, not a mutable
        # current rubric. Practice may intentionally use its own prepared case.
        snapshot = (original.case_snapshot if original and original.case_prompt_id == case.id and original.case_snapshot
            else snapshot_case(case))
        prepared = snapshot.get("rubric", {})
        concept = self.db.get(Concept, session.concept_id)
        lesson = LESSONS.get(concept.slug) if concept else None
        support = self.db.query(Intervention).filter_by(session_id=session.id).order_by(Intervention.created_at).all()
        source_assessments = [{
            "criterion": c.criterion, "skill_id": c.skill_id, "rating": c.rating,
            "met": c.met, "evidence": c.evidence, "status": c.status,
            "question_part_id": getattr(c, "question_part_id", None),
            "coverage": getattr(c, "coverage", None),
            "issue_type": getattr(c, "issue_type", None),
            "demonstrated_explanation": getattr(c, "demonstrated_explanation", None),
            "explanation": getattr(c, "explanation", None),
            "next_action": getattr(c, "next_action", None),
        } for c in (original.criterion_assessments if original else [])]
        same_case = bool(original and original.case_prompt_id == case.id)
        latest_revision = self.db.query(Attempt).filter_by(session_id=session.id, stage="investigate",
            case_prompt_id=case.id).order_by(Attempt.created_at.desc(), Attempt.id.desc()).first()
        teaching_context = {
            "submission_state": {"current_message_kind": "conversation_reply", "revision_submitted": latest_revision is not None,
                "saved_revision_attempt_id": latest_revision.id if latest_revision else None,
                "next_action_label": "Review and revise my answer"},
            "revision_consistency": self._revision_conflicts(original, latest_revision),
            "latest_revision": {"attempt_id": latest_revision.id, "answer": latest_revision.answer_text} if latest_revision else None,
            "version": "2026-10-20.1", "case_id": snapshot.get("id"), "case_version": snapshot.get("version"),
            "rubric_version": prepared.get("version"), "content_review_status": snapshot.get("review_status", "unreviewed"),
            "source_provenance": "frozen_attempt" if original and original.case_snapshot and original.case_prompt_id == case.id else "current_prepared_case",
            "reference_answer": prepared.get("reference_answer", ""), "criteria": prepared.get("criteria", []),
            "question_parts": snapshot.get("question_parts"),
            "question_parts_coverage": getattr(original, "question_parts_coverage", None) if same_case else None,
            "assessment_attempt_id": original.id if same_case else None,
            "assessments": source_assessments if same_case else [],
            "source_attempt": {"attempt_id": original.id, "case_id": original.case_prompt_id,
                "case_version": (original.case_snapshot or {}).get("version"),
                "assessments": source_assessments,
                "question_parts_coverage": getattr(original, "question_parts_coverage", None)} if original else None,
            "lesson": {"version": RESOURCE_VERSION, "source": "AI-authored, unreviewed", **lesson} if lesson else None,
            "help_history": [{"type": item.intervention_type, "title": item.title, "status": item.status,
                "content": (item.content or "")[-6000:], "opened": item.opened_at is not None,
                "completed": item.completed_at is not None, "created_at": item.created_at.isoformat()} for item in support[-12:]],
        }
        history = [{"role": m.role, "content": m.content} for m in self.db.query(Message).filter_by(session_id=session.id).order_by(Message.created_at, Message.id)]
        self.db.commit()
        reply = await self.ai.tutor_conversation(scenario=snapshot["scenario_text"], assumptions=snapshot.get("assumptions") or [],
            original_answer=original.answer_text if original else "", gap_description=gap.description if gap else None,
            probe_text=gap.probe_text if gap else None, history=history, action=turn.action, user_text=turn.text,
            teaching_context=teaching_context)
        text = reply.message
        if reply.diagram_ascii and reply.diagram_ascii not in text:
            text += "\n\n" + reply.diagram_ascii
        self._message(session, messages, text, reply.status)
        actual = getattr(reply, "assistance_kind", "unknown")
        kind = actual if actual in {"hint", "follow_up", "teaching"} else "tutoring_unknown"
        if turn.action == "request_teaching":
            kind = "teaching"  # Never understate an explicit request for teaching.
        title = f"{kind.replace('_', ' ').capitalize()} (requested: {turn.action.replace('_', ' ')})"
        self._intervention(session, kind, title, text,
            "delivered" if reply.status == "complete" else reply.status)
        if gap and turn.action == "correct_ai":
            gap.status = "challenged"

    def _practice(self, session, messages):
        used = {a.case_prompt_id for a in self.db.query(Attempt).filter_by(session_id=session.id, stage="practice")}
        current = self.db.get(CasePrompt, session.current_prompt_id)
        if current and current.case_type in PRACTICE_TYPES:
            self._message(session, messages, "Complete the current prepared practice before requesting another one.")
            return
        cases = self.db.query(CasePrompt).filter_by(concept_id=session.concept_id, stage="investigate", active=True).filter(CasePrompt.case_type.in_(PRACTICE_TYPES)).order_by(CasePrompt.sort_order).all()
        case = next((c for c in cases if c.id not in used), None)
        if not case:
            self._message(session, messages, "All prepared practice has been attempted. Continue the conversation or submit your revised explanation.")
            return
        session.current_prompt_id = case.id
        self._intervention(session, "practice", "Prepared guided practice", case.scenario_text)
        self._message(session, messages, "Here is a prepared practice exercise. It is guided learning evidence, not an independent transfer assessment.")

    def _snapshot_opened_guide(self, item):
        """Append the actual opened version, including legacy ID-based offers."""
        prefix = "/v1/resources/"
        slug = item.url[len(prefix):] if item.url and item.url.startswith(prefix) else None
        lesson = LESSONS.get(slug)
        marker = f"Opened guide snapshot ({RESOURCE_VERSION})"
        if lesson and marker not in (item.content or ""):
            snapshot = {"version": RESOURCE_VERSION, "source": "AI-authored, unreviewed",
                "opened_at": datetime.now(timezone.utc).isoformat(), **lesson}
            item.content = (item.content or "") + f"\n\n{marker}:\n" + json.dumps(snapshot, ensure_ascii=False)

    def _resource(self, session, messages, offer_message=True):
        concept = self.db.get(Concept, session.concept_id)
        url = f"/v1/resources/{concept.slug}"
        text = f"[Open the prepared {concept.title} guide]({url}). Reading it is optional; opening a link alone does not prove learning."
        item = self.db.query(Intervention).filter_by(session_id=session.id, intervention_type="resource", url=url).order_by(Intervention.created_at).first()
        if not item:
            lesson = LESSONS.get(concept.slug)
            content = text
            if lesson:
                content += "\n\n" + json.dumps({"version": RESOURCE_VERSION, "source": "AI-authored, unreviewed", **lesson}, ensure_ascii=False)
            item = self._intervention(session, "resource", concept.title, content, status="offered", url=url)
        if offer_message:
            self._message(session, messages, text)
            return {"id": item.id, "type": "resource", "title": item.title, "content": text, "url": url}
        return item
