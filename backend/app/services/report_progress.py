"""Describe chronology from saved evidence; no model calls or mastery claims."""


def learning_progress(reports, expected_by_attempt, transfer_is_independent):
    stages = {stage: [a for a in reports if a.stage == stage and a.case_type not in ('practice', 'guided_practice')]
              for stage in ('diagnostic', 'investigate', 'apply')}

    def rows(stage):
        return [c for a in stages[stage] for c in a.criteria if not (c.get('skill_id') or '').startswith('exercise:')]

    def key(c):
        return c.get('skill_id') or c['criterion']

    def label(skill):
        return skill.replace('_', ' ')

    def demonstrated(c):
        return c.get('met') is True and c.get('rating') == 'demonstrated' and c.get('issue_type') != 'technical_failure'

    def difficulties(stage):
        return {key(c) for c in rows(stage) if c.get('rating') in
                ('not_addressed', 'partially_demonstrated', 'ambiguous_needs_clarification') and not demonstrated(c)}

    def stage_demonstrates(stage, skill):
        relevant = []
        for attempt in stages[stage]:
            expected = {c['criterion'] for c in expected_by_attempt.get(attempt.id, []) if key(c) == skill}
            actual = [c for c in attempt.criteria if key(c) == skill]
            if not expected and not actual:
                continue
            # Do not infer success from one row when a same-skill criterion is missing.
            if not expected or {c['criterion'] for c in actual} != expected or not all(demonstrated(c) for c in actual):
                return False
            if attempt.processing_status != 'complete':
                return False
            relevant.extend(actual)
        return bool(relevant)

    initial_skills = difficulties('diagnostic')
    initial_parts = []
    for rating, heading in [('not_addressed', 'Initially omitted'), ('partially_demonstrated', 'Initially incomplete'),
                            ('ambiguous_needs_clarification', 'Initially unclear')]:
        names = sorted({label(key(c)) for c in rows('diagnostic') if c.get('rating') == rating})
        if names:
            initial_parts.append(f"{heading}: {', '.join(names)}")
    initial = '; '.join(initial_parts) + '.' if initial_parts else 'No initial reasoning difficulty was established by available assessments.'

    later, remaining = [], []
    needs_case = set()
    for skill in sorted(initial_skills | difficulties('apply')):
        revision_met = stage_demonstrates('investigate', skill)
        transfer_met = stage_demonstrates('apply', skill)
        evidence = []
        if revision_met:
            evidence.append('demonstrated in the supported revision')
        if transfer_met:
            evidence.append('independently demonstrated on the unfamiliar case' if transfer_is_independent
                            else 'demonstrated on the unfamiliar case with support or unknown support provenance')
        if evidence:
            later.append(f"{label(skill)}: {'; '.join(evidence)}.")
        if transfer_met and transfer_is_independent:
            continue
        if skill in difficulties('apply'):
            remaining.append(f'{label(skill)} (still incomplete or unclear on the unfamiliar case)')
        elif revision_met:
            remaining.append(f'{label(skill)} (supported revision evidence; independent recheck needed)')
        else:
            remaining.append(f'{label(skill)} (earlier difficulty has no successful independent recheck)')
        needs_case.add(skill)

    unavailable = any(a.unavailable_criteria_count or any(c.get('rating') == 'technical_failure' for c in a.criteria)
                      for group in stages.values() for a in group)
    notices = ('Some criterion assessments are missing or unavailable. This is an assessment issue, not a learner mistake.'
               if unavailable else '')
    steps = []
    if needs_case:
        steps.append(f"Try a different prepared, unseen case focused on {', '.join(label(s) for s in sorted(needs_case))}; explain your reasoning independently.")
    elif not stages['apply']:
        steps.append('Complete a prepared unfamiliar case independently before drawing a transfer conclusion.')
    elif not transfer_is_independent:
        steps.append('Complete a different unfamiliar case independently; current transfer assistance is recorded or unknown.')
    if unavailable:
        steps.append('Separately, request reassessment of the saved answers with missing or unavailable criterion judgments.')
    if not steps:
        steps.append('No additional remediation is indicated by these tested criteria. A short session does not establish retained learning or mastery.')

    revision_note = ('The revised answer is supported evidence. Its correctness or similarity to a tutor explanation does not establish independent learning; use unfamiliar-case evidence separately.'
                     if stages['investigate'] else 'No revised answer was submitted.')
    return {
        'initial_difficulties': initial,
        'later_evidence': ' '.join(later) if later else ('No matching later evidence has yet demonstrated these initially uncertain skills.' if initial_skills else 'No initial difficulty required a later comparison.'),
        'remaining_gaps': '; '.join(remaining) + '.' if remaining else 'No unresolved reasoning difficulty is established by the available tested evidence.',
        'assessment_notices': notices,
        'revision_note': revision_note,
        'next_steps': steps,
        # Historical compatibility fields remain explicitly historical.
        'missing_or_incorrect': initial,
        'recommended_next_step': ' '.join(steps),
    }
