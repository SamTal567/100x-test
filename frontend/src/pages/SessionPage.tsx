import React, { useCallback, useEffect, useRef, useState } from 'react'
import { api, ApiError } from '../api/client'
import { StageProgressBar } from '../components/StageProgressBar'
import { VoiceRecorder } from '../components/VoiceRecorder'
import { PresetDiagramView } from '../components/PresetDiagramView'
import { ClozeExerciseView } from '../components/ClozeExerciseView'
import { SessionTranscript } from '../components/SessionTranscript'
import { AttemptView, ReportView } from '../components/ReportView'
import { DiagnosticFeedback } from '../components/DiagnosticFeedback'
import { TrackedResourceLink } from '../components/TrackedResourceLink'
import { applyDictation, editDraftText } from '../lib/dictation'
import { draftKey, emptyDraft, pendingKey, readStored, safeResourceUrl, savedPending, writeStored } from '../lib/sessionDrafts'
import type { AnswerDraft } from '../lib/sessionDrafts'
import type { CasePrompt, SessionDetail, SessionReport, TurnRequest } from '../types'

interface SessionPageProps {
  sessionId: string
  onBackToCatalogue: () => void
  onOpenReviewer?: () => void
  onOpenSession?: (id: string) => void
  reviewRevision?: number
}

type Action = TurnRequest['action']
type AnswerPayload = Pick<TurnRequest, 'text' | 'diagram_state' | 'cloze_state' | 'input_mode' | 'transcription_id' | 'transcription_segments' | 'resource_id'>
type Send = (action: Action, payload?: AnswerPayload) => Promise<boolean>

const PromptView: React.FC<{ prompt: CasePrompt; children?: React.ReactNode }> = ({ prompt, children }) => <section className="scenario-card" aria-label="Current scenario">
  <div className="scenario-card-header"><span className="scenario-label-badge">{prompt.case_type.replaceAll('_', ' ')} case</span><span className="badge badge-provisional">{prompt.review_status === 'reviewed' ? 'Human reviewed content' : 'Authored content — awaiting human review'}</span></div>
  <div className="scenario-text" style={{ whiteSpace: 'pre-wrap' }}>{prompt.scenario_text}</div>
  {prompt.assumptions?.length ? <div className="scenario-assumptions"><strong>Stated assumptions</strong><ul>{prompt.assumptions.map((assumption, index) => <li key={index}>{assumption}</li>)}</ul></div> : null}
  {children}
</section>

// Keyed by session + prompt + action: practice cannot replace the revision draft.
const AnswerComposer: React.FC<{
  sessionId: string; prompt?: CasePrompt | null; action: Action; label: string; submitLabel: string;
  disabled: boolean; send: Send; exercises?: boolean; voice?: boolean
}> = ({ sessionId, prompt, action, label, submitLabel, disabled, send, exercises = false, voice = true }) => {
  const storageKey = draftKey(sessionId, prompt?.id, action)
  const [draft, setDraft] = useState<AnswerDraft>(() => ({ ...emptyDraft, ...readStored<AnswerDraft>(storageKey) }))
  const [voiceOpen, setVoiceOpen] = useState(false)
  const update = (patch: Partial<AnswerDraft>) => setDraft(previous => {
    const next = { ...previous, ...patch }
    writeStored(storageKey, next)
    return next
  })
  const submit = async (event: React.FormEvent) => {
    event.preventDefault()
    if (!draft.text.trim() || disabled || voiceOpen) return
    const success = await send(action, {
      text: draft.text.trim(), diagram_state: exercises ? draft.diagram : null,
      cloze_state: exercises ? draft.cloze : null, input_mode: draft.inputMode,
      transcription_id: draft.transcriptionId,
      transcription_segments: draft.transcriptionSegments || [],
    })
    if (success) { writeStored(storageKey, null); setDraft(emptyDraft); setVoiceOpen(false) }
  }
  const inputId = `${action}-${prompt?.id || 'chat'}-input`
  return <form className="answer-card" onSubmit={submit} aria-label={label}>
    {exercises && prompt?.diagram_preset && <PresetDiagramView diagram={prompt.diagram_preset} value={draft.diagram} onChange={diagram => update({ diagram })} readOnly={disabled} />}
    {exercises && prompt?.cloze_preset && <ClozeExerciseView cloze={prompt.cloze_preset} value={draft.cloze} onChange={cloze => update({ cloze })} readOnly={disabled} />}
    <div className="answer-header-row"><label className="answer-label" htmlFor={inputId}>{label}</label><span className="answer-guide-tip">Draft saved in this browser tab</span></div>
    <textarea id={inputId} className="textarea answer-textarea" rows={action === 'answer_probe' || action === 'clarify' || action === 'correct_ai' ? 3 : 6} value={draft.text} required disabled={disabled} autoFocus={action === 'clarify' || action === 'correct_ai'} onChange={event => update(editDraftText(draft, event.target.value))} aria-describedby={`${inputId}-help`} />
    <p id={`${inputId}-help`} className="muted-note">{action === 'answer_probe' ? 'Send a reply or answer the follow-up. This keeps the tutoring conversation open.' : exercises ? 'Explain your reasoning in words as well as making any diagram or blank selections.' : action === 'clarify' ? 'Ask about the scenario assumptions. A clarification is recorded separately from your answer.' : action === 'correct_ai' ? 'Point out the specific part of your answer the tutor misunderstood.' : 'Explain the mechanism and why it applies to this case.'}</p>
    {voiceOpen && !disabled && <VoiceRecorder sessionId={sessionId} existingText={draft.text} onConfirmedTranscript={(text, transcriptionId, mode) => { update(applyDictation(draft, text, transcriptionId, mode)); setVoiceOpen(false) }} onCancel={() => setVoiceOpen(false)} />}
    {voiceOpen && <p className="muted-note">Add or cancel the recording before submitting your answer.</p>}
    <div className="answer-actions-bar"><div className="secondary-inputs-group">{voice && !voiceOpen && <button type="button" className="btn btn-secondary btn-sm" disabled={disabled} onClick={() => setVoiceOpen(true)}>🎙️ {draft.text.trim() ? 'Add more by voice' : 'Dictate'}</button>}</div><button type="submit" className="btn btn-primary" disabled={disabled || voiceOpen || !draft.text.trim()}>{submitLabel}</button></div>
  </form>
}

export const SessionPage: React.FC<SessionPageProps> = ({ sessionId, onBackToCatalogue, onOpenSession, reviewRevision = 0 }) => {
  const [session, setSession] = useState<SessionDetail | null>(null)
  const [report, setReport] = useState<SessionReport | null>(null)
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [pending, setPending] = useState<TurnRequest | null>(() => savedPending(sessionId))
  const [utility, setUtility] = useState<'clarify' | 'correct_ai' | null>(null)
  const headingRef = useRef<HTMLHeadingElement>(null)
  const chatRef = useRef<HTMLDivElement>(null)

  const applyHydration = useCallback(async (state: SessionDetail) => {
    setSession(state)
    if (state.pending_turn) {
      setPending(state.pending_turn)
      writeStored(pendingKey(sessionId), state.pending_turn)
    }
    try { setReport(await api.getSessionReport(sessionId)) }
    catch (reason) { if (state.stage === 'review' || state.stage === 'completed') throw reason }
    return state
  }, [sessionId])

  const hydrate = async () => applyHydration(await api.getSession(sessionId))

  useEffect(() => {
    let alive = true
    api.getSession(sessionId).then(state => { if (alive) return applyHydration(state) }).catch(reason => { if (alive) setError(`Could not restore this session: ${reason instanceof Error ? reason.message : String(reason)}`) }).finally(() => { if (alive) setLoading(false) })
    return () => { alive = false }
  }, [applyHydration, sessionId, reviewRevision])

  const execute = async (request: TurnRequest): Promise<boolean> => {
    if (submitting) return false
    setSubmitting(true)
    setError(null)
    setPending(request)
    writeStored(pendingKey(sessionId), request)
    try {
      const response = await api.submitTurn(sessionId, request)
      const failed = ['pending', 'processing', 'failed', 'error'].includes(response.processing_status)
      setSession(previous => previous ? {
        ...previous, stage: response.stage, version: response.version,
        diagnostic_index: response.diagnostic_index, diagnostic_total: response.diagnostic_total, current_prompt: response.current_prompt,
        allowed_actions: response.allowed_actions, evidence_cards: response.evidence_cards,
        processing_status: response.processing_status, practice_active: response.practice_active,
        messages: [...(previous.messages || []), ...response.messages.filter(message => !(previous.messages || []).some(old => old.id === message.id))],
      } : previous)
      if (!failed) { setPending(null); writeStored(pendingKey(sessionId), null); setUtility(null) }
      try { await hydrate() } catch { setError('The request was saved, but the latest session could not be refreshed. Reload to restore the saved state.') }
      if (failed) setError('Your submission is saved. Processing did not finish. Retry the saved request to resume it without submitting another answer.')
      if (!failed && (response.stage !== session?.stage || response.current_prompt?.id !== session?.current_prompt?.id)) headingRef.current?.focus()
      return !failed
    } catch (reason) {
      // A timeout can happen after persistence. Retain exact ID, version and body.
      setError(`The request could not be confirmed: ${reason instanceof Error ? reason.message : String(reason)}. Your draft and exact request are retained.`)
      try {
        const state = await hydrate()
        if (reason instanceof ApiError && [400, 401, 403, 404, 409, 422].includes(reason.status) && !state.pending_turn) {
          setPending(null)
          writeStored(pendingKey(sessionId), null)
          setError(`The server rejected this request: ${reason.message}. Your draft is preserved; review it and submit again using the refreshed session.`)
        }
      } catch { /* The local exact request remains retryable offline. */ }
      return false
    } finally { setSubmitting(false) }
  }

  const send: Send = async (action, payload = {}) => {
    const finishFailedProcessing = action === 'finish_session' && session?.processing_status === 'failed'
    if (!session || (pending && !finishFailedProcessing) || submitting || !(session.allowed_actions || []).includes(action)) return false
    return execute({ client_turn_id: crypto.randomUUID(), expected_version: session.version,
      prompt_id: session.current_prompt?.id || null, action, ...payload })
  }

  const composer = (action: Action, label: string, submitLabel: string, exercises = false, voice = true) => <AnswerComposer key={`${sessionId}:${session?.current_prompt?.id}:${action}`} sessionId={sessionId} prompt={session?.current_prompt} action={action} label={label} submitLabel={submitLabel} exercises={exercises} voice={voice} disabled={submitting || Boolean(pending)} send={send} />
  const can = (action: Action) => session?.allowed_actions?.includes(action) || false
  const openResource = async (url: string) => {
    const canonical = url.split('#')[0]
    const offered = report?.interventions_used.find(item => item.url === canonical && item.type === 'resource')
    return send('resource_opened', { resource_id: offered?.id, text: canonical })
  }
  const actionsDisabled = submitting || Boolean(pending)
  const prompt = session?.current_prompt
  const terminal = session?.stage === 'review' || session?.stage === 'completed'
  const sourceIds = new Set((session?.evidence_cards || []).map(card => card.source_attempt_id).filter(Boolean))
  for (const gap of session?.gaps || []) if (gap.source_attempt_id) sourceIds.add(gap.source_attempt_id)
  const sourceAttempts = (session?.attempts || []).filter(attempt => sourceIds.has(attempt.id))
  const recordedStages = [...new Set((session?.attempts || []).map(attempt => attempt.stage))]
  if ((session?.messages || []).some(message => message.stage === 'investigate')) recordedStages.push('investigate')

  if (loading) return <div className="loading-container" role="status"><span className="spinner" />Restoring learning session…</div>
  if (!session) return <div className="error-banner" role="alert"><span>{error || 'This session could not be loaded.'}</span><button className="btn btn-secondary" onClick={onBackToCatalogue}>Catalogue</button></div>

  const stageTitle = terminal ? 'Evidence report' : session.stage === 'diagnostic' ? `Case ${session.diagnostic_index + 1}${session.diagnostic_total ? ` of ${session.diagnostic_total}` : ''} — Baseline reasoning` : session.stage === 'apply' ? 'Unfamiliar Case — Application & Evaluation' : session.practice_active ? 'Guided practice — Support is recorded' : 'Investigation and tutoring'
  return <div className="session-page-wrapper">
    <div className="card session-topbar mb-4"><div className="session-topbar-header"><div className="session-title-group"><button type="button" className="btn btn-secondary btn-sm" onClick={onBackToCatalogue}>← Catalogue</button><div><h1 ref={headingRef} tabIndex={-1} className="session-concept-title">{session.concept_title || 'Concept Check'}</h1><div className="session-stage-subtitle">{stageTitle}</div></div></div></div><div className="session-progress-wrapper"><StageProgressBar currentStage={session.stage} recordedStages={recordedStages} /></div></div>
    {error && <div className="error-banner mb-4" role="alert"><span>{error}</span></div>}
    {pending && <div className="card recovery-card mb-4" role="status"><strong>Saved request awaiting confirmation</strong><p>{submitting ? 'Saving and processing your request…' : 'Retry resumes this exact request and preserves its original submission identifier.'}</p><div className="action-wrap"><button type="button" className="btn btn-secondary" disabled={submitting} onClick={() => execute(pending)}>Retry saved request</button>{terminal && can('finish_session') && session.processing_status === 'failed' && <button type="button" className="btn btn-secondary" disabled={submitting} onClick={() => send('finish_session')}>Finish partial report</button>}</div></div>}
    {!terminal && <div className="stage-content-container">
      {prompt && <PromptView prompt={prompt} />}
      {session.stage === 'investigate' && <>
        <DiagnosticFeedback
          attempts={session.attempts || []}
          conceptSlug={session.concept_slug}
          conceptTitle={session.concept_title}
          onScrollToChat={() => chatRef.current?.scrollIntoView({ behavior: 'smooth' })}
          onRetryAssessment={can('retry_processing') ? () => { void send('retry_processing') } : undefined}
          disabled={actionsDisabled}
          onOpenResource={openResource}
        />
        {sourceAttempts.map(attempt => <details key={attempt.id} className="earlier-answers-panel"><summary className="earlier-answers-summary">Your original answer for this concern</summary><AttemptView attempt={attempt} anchor={false} /></details>)}
        {(session.evidence_cards || []).map((card, index) => <div className="gap-finding-card" key={card.id || index}><strong>{card.title || card.gap_description || 'Possible concern to investigate'}</strong>{card.evidence_quote && <blockquote>{card.evidence_quote}</blockquote>}{card.probe_question && <p>Follow-up: {card.probe_question}</p>}</div>)}
      </>}
      <div ref={chatRef}>
        <SessionTranscript messages={session.messages || []} stage={session.stage} onOpenResource={openResource} disabled={actionsDisabled || !can('resource_opened')} />
      </div>
      {session.stage === 'investigate' && <div className="tutoring-actions action-wrap">
        {([['request_hint', 'Request a hint'], ['request_teaching', 'Ask for an explanation'], ['request_practice', 'Try guided practice'], ['request_help', 'Suggest a resource']] as const).filter(([action]) => can(action)).map(([action, label]) => <button type="button" key={action} className="btn btn-secondary btn-sm" disabled={actionsDisabled} onClick={() => send(action)}>{label}</button>)}
      </div>}
      {session.stage === 'investigate' && report?.interventions_used.filter(item => item.url && safeResourceUrl(item.url)).map(item => <section className="card recovery-card" key={item.id || item.url} aria-label="Suggested resource"><strong>{item.title || 'Authored resource'}</strong><p className="muted-note">Reading is optional. Opening is recorded separately from your self-reported completion; neither establishes understanding.</p><div className="action-wrap"><TrackedResourceLink url={safeResourceUrl(item.url!)!} onOpenResource={openResource} disabled={actionsDisabled || !can('resource_opened')}>Open resource</TrackedResourceLink>{can('resource_completed') && <button className="btn btn-secondary btn-sm" disabled={actionsDisabled || item.completed} onClick={() => send('resource_completed', { resource_id: item.resource_id || item.id })}>{item.completed ? 'Marked complete (self-reported)' : 'Mark resource complete'}</button>}</div></section>)}
      <div className="action-wrap">{can('clarify') && <button className="btn btn-secondary btn-sm" disabled={actionsDisabled} aria-expanded={utility === 'clarify'} onClick={() => setUtility(utility === 'clarify' ? null : 'clarify')}>Clarify the scenario</button>}{can('correct_ai') && <button className="btn btn-secondary btn-sm" disabled={actionsDisabled} aria-expanded={utility === 'correct_ai'} onClick={() => setUtility(utility === 'correct_ai' ? null : 'correct_ai')}>Correct the AI’s interpretation</button>}</div>
      {utility && can(utility) && composer(utility, utility === 'clarify' ? 'Question about the scenario' : 'Correction of the AI’s interpretation', utility === 'clarify' ? 'Send clarification question' : 'Send correction', false, false)}
      {session.stage === 'diagnostic' && can('submit_answer') && composer('submit_answer', 'Explain what happens and why', 'Save baseline answer →', true)}
      {session.stage === 'investigate' && <>
        {can('answer_probe') && composer('answer_probe', 'Reply to the tutor', 'Send reply')}
        {session.practice_active && can('submit_practice') && composer('submit_practice', 'Practice reasoning and justification', 'Submit guided practice', true)}
        {!session.practice_active && can('submit_answer') && <details className="revision-panel" open><summary>Ready to revise the original answer?</summary>{composer('submit_answer', 'Revised explanation of the original case', 'Submit revised answer →', true)}</details>}
        {can('continue') && <button type="button" className="btn btn-primary" disabled={actionsDisabled} onClick={() => send('continue')}>⚡ Ready for unfamiliar case challenge →</button>}
      </>}
      {session.stage === 'apply' && can('submit_answer') && composer('submit_answer', 'Explain what happens in this unfamiliar case and why', 'Submit unfamiliar case & view comparison report →', true)}

      {(session.attempts || []).length > 0 && <details className="earlier-answers-panel"><summary className="earlier-answers-summary">Earlier submitted answers ({session.attempts?.length})</summary><div className="attempts-stack">{session.attempts?.map(attempt => <AttemptView key={attempt.id} attempt={attempt} />)}</div></details>}
      {can('finish_session') && <div className="finish-session-panel"><p>You can finish with the evidence collected so far. Unattempted stages will remain unassessed.</p>{pending && session.processing_status === 'failed' && <p>Failed processing will stop. Your saved answer remains in the partial evidence report.</p>}<button type="button" className="btn btn-secondary" disabled={submitting || (Boolean(pending) && session.processing_status !== 'failed')} onClick={() => send('finish_session')}>{pending && session.processing_status === 'failed' ? 'Finish partial report' : 'Finish with current evidence'}</button></div>}
    </div>}
    {terminal && (report ? <ReportView report={report} onBack={onBackToCatalogue} onOpenSession={onOpenSession} onRetryAssessments={can('retry_processing') ? () => { void send('retry_processing') } : undefined} retryDisabled={actionsDisabled} /> : <div className="card" role="status"><p>The saved report could not be loaded.</p><button className="btn btn-secondary" onClick={() => hydrate().catch(reason => setError(String(reason)))}>Reload report</button></div>)}
    {terminal && <SessionTranscript messages={session.messages || []} stage={session.stage} />}
  </div>
}
