import React, { useCallback, useEffect, useRef, useState } from 'react'
import { api, ApiError } from '../api/client'
import { StageProgressBar } from '../components/StageProgressBar'
import { VoiceRecorder } from '../components/VoiceRecorder'
import { PresetDiagramView } from '../components/PresetDiagramView'
import { ClozeExerciseView } from '../components/ClozeExerciseView'
import { SessionTranscript } from '../components/SessionTranscript'
import { AttemptView, ReportView } from '../components/ReportView'
import { DiagnosticFeedback } from '../components/DiagnosticFeedback'
import { HelpMenu } from '../components/HelpMenu'
import { initialTutoringView, tutoringViewKey } from '../lib/tutoringView'
import type { TutoringView } from '../lib/tutoringView'
import { applyDictation, editDraftText } from '../lib/dictation'
import { openTrackedResource } from '../lib/trackedResources'
import { draftKey, emptyDraft, pendingKey, readStored, savedPending, writeStored } from '../lib/sessionDrafts'
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

function parseScenarioPrompt(text: string): { background: string; task: string | null } {
  if (!text) return { background: '', task: null }
  const match = text.match(/(?:^|\n+)(?:Your\s+Task|Task):\s*/i)
  if (!match || match.index === undefined) {
    return { background: text, task: null }
  }
  const background = text.slice(0, match.index).trim()
  const task = text.slice(match.index + match[0].length).trim()
  return { background, task }
}

export const PromptView: React.FC<{ prompt: CasePrompt; children?: React.ReactNode }> = ({ prompt, children }) => {
  const { background, task } = parseScenarioPrompt(prompt.scenario_text)
  return (
    <section className="scenario-card" aria-label="Current scenario">
      <div className="scenario-card-header">
        <span className="scenario-label-badge">{prompt.case_type.replaceAll('_', ' ')} case</span>
        <span className="badge badge-provisional">
          {prompt.review_status === 'reviewed' ? 'Human reviewed content' : 'Authored content — awaiting human review'}
        </span>
      </div>
      {background ? <div className="scenario-text" style={{ whiteSpace: 'pre-wrap' }}>{background}</div> : null}
      {task ? (
        <div className="task-accent-card" role="region" aria-label="Your task">
          <div className="task-accent-header">
            <span className="task-accent-icon" aria-hidden="true">🎯</span>
            <strong className="task-accent-title">Your Task</strong>
          </div>
          <div className="task-accent-body">{task}</div>
        </div>
      ) : (
        !background && <div className="scenario-text" style={{ whiteSpace: 'pre-wrap' }}>{prompt.scenario_text}</div>
      )}
      {prompt.assumptions?.length ? (
        <div className="scenario-assumptions scenario-assumptions-card" role="region" aria-label="Stated assumptions">
          <div className="scenario-assumptions-header">
            <strong>Stated assumptions</strong>
          </div>
          <ul className="scenario-assumptions-list">
            {prompt.assumptions.map((assumption, index) => (
              <li key={index} className="scenario-assumption-item">
                <span className="assumption-checkmark" aria-hidden="true">✓</span>
                <span>{assumption}</span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      {children}
    </section>
  )
}

export const EvaluationProgressLoader: React.FC = () => {
  const [elapsed, setElapsed] = useState(0)
  useEffect(() => {
    const start = Date.now()
    const timer = setInterval(() => {
      setElapsed(Math.floor((Date.now() - start) / 1000))
    }, 500)
    return () => clearInterval(timer)
  }, [])

  const activeStep = elapsed >= 12 ? 3 : elapsed >= 4 ? 2 : 1

  return (
    <div className="card evaluation-loader-card mb-4" role="status" aria-live="polite">
      <div className="evaluation-loader-header">
        <span className="spinner-inline" />
        <strong className="evaluation-loader-title">Evaluating your response...</strong>
      </div>
      <div className="evaluation-steps-list">
        <div className={`evaluation-step ${activeStep > 1 ? 'completed' : activeStep === 1 ? 'active' : 'upcoming'}`}>
          <span className="step-badge">{activeStep > 1 ? '✓' : '1'}</span>
          <span className="step-label">Saving your draft securely...</span>
        </div>
        <div className={`evaluation-step ${activeStep > 2 ? 'completed' : activeStep === 2 ? 'active' : 'upcoming'}`}>
          <span className="step-badge">{activeStep > 2 ? '✓' : '2'}</span>
          <span className="step-label">AI Tutor is analyzing your explanation &amp; criteria...</span>
        </div>
        <div className={`evaluation-step ${activeStep === 3 ? 'active' : 'upcoming'}`}>
          <span className="step-badge">3</span>
          <span className="step-label">Synthesizing personalized feedback and follow-up probes...</span>
        </div>
      </div>
      <div className="evaluation-pulse-bar" aria-hidden="true">
        <div className="evaluation-pulse-fill" />
      </div>
    </div>
  )
}

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
    <div className="answer-actions-bar">
      <div className="secondary-inputs-group">
        {voice && !voiceOpen && (
          <div className="voice-input-control">
            <button type="button" className="btn btn-secondary btn-sm" disabled={disabled} onClick={() => setVoiceOpen(true)}>
              🎙️ {draft.text.trim() ? 'Add more by voice' : 'Dictate'}
            </button>
            <span className="voice-dictation-helper-tip">
              Speak naturally. Dictation appends to your draft so you can review and edit before sending.
            </span>
          </div>
        )}
      </div>
      <button type="submit" className="btn btn-primary" disabled={disabled || voiceOpen || !draft.text.trim()}>{submitLabel}</button>
    </div>
  </form>
}

export const SessionPage: React.FC<SessionPageProps> = ({ sessionId, onBackToCatalogue, onOpenSession, reviewRevision = 0 }) => {
  const [session, setSession] = useState<SessionDetail | null>(null)
  const [report, setReport] = useState<SessionReport | null>(null)
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [resourceError, setResourceError] = useState<string | null>(null)
  const [pending, setPending] = useState<TurnRequest | null>(() => savedPending(sessionId))
  const [utility, setUtility] = useState<'clarify' | 'correct_ai' | null>(null)
  const [investigateMode, setInvestigateMode] = useState<TutoringView>('summary')
  const headingRef = useRef<HTMLHeadingElement>(null)
  const viewInitialized = useRef(false)
  const changeTutoringView = (view: TutoringView) => {
    setInvestigateMode(view)
    writeStored(tutoringViewKey(sessionId), view)
    setUtility(null)
    headingRef.current?.focus({ preventScroll: true })
    window.scrollTo({ top: 0, behavior: 'instant' })
  }

  const applyHydration = useCallback(async (state: SessionDetail) => {
    setSession(state)
    if (!viewInitialized.current) {
      setInvestigateMode(initialTutoringView(readStored(tutoringViewKey(sessionId)), state.messages || []))
      viewInitialized.current = true
    }
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
      if (!failed && (response.stage !== session?.stage || response.current_prompt?.id !== session?.current_prompt?.id)) {
        headingRef.current?.focus()
        if (response.stage === 'investigate') changeTutoringView(session?.stage === 'diagnostic' ? 'summary' : 'tutoring')
      }
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
  const confirmResourceOpening = async (url: string): Promise<boolean> => {
    const canonical = url.split('#')[0]
    setResourceError(null)
    const offered = report?.interventions_used.find(item => item.url === canonical && item.type === 'resource')
    const success = await send('resource_opened', { resource_id: offered?.id, text: canonical })
    if (!success) {
      setResourceError('Could not record guide opening. Please retry.')
      return false
    }
    return true
  }
  const openConceptGuide = async (url: string): Promise<boolean> => {
    const canonical = url.split('#')[0]
    setResourceError(null)
    const success = await openTrackedResource(
      canonical,
      () => confirmResourceOpening(canonical)
    )
    if (!success) {
      setResourceError(err => err || 'Could not open the concept guide. Please retry or check popup permissions.')
    }
    return success
  }
  const actionsDisabled = submitting || Boolean(pending)
  const prompt = session?.current_prompt
  const terminal = session?.stage === 'review' || session?.stage === 'completed'
  const sourceIds = new Set((session?.evidence_cards || []).map(card => card.source_attempt_id).filter(Boolean))
  for (const gap of session?.gaps || []) if (gap.source_attempt_id) sourceIds.add(gap.source_attempt_id)
  const sourceAttempts = (session?.attempts || []).filter(attempt => sourceIds.has(attempt.id))
  const recordedStages = [...new Set((session?.attempts || []).map(attempt => attempt.stage))]
  if ((session?.messages || []).some(message => message.stage === 'investigate')) recordedStages.push('investigate')
  const completedStages = [...new Set((session?.attempts || []).map(attempt => attempt.stage))]
  const attemptedStages = [...new Set([...completedStages, ...((session?.messages || []).map(message => message.stage))])]

  const firstTutorProbe =
    session?.messages?.find(m => m.stage === 'investigate' && (m.role === 'tutor' || m.role === 'system'))?.content ||
    session?.evidence_cards?.[0]?.probe_question

  if (loading) return <div className="loading-container" role="status"><span className="spinner" />Restoring learning session…</div>
  if (!session) return <div className="error-banner" role="alert"><span>{error || 'This session could not be loaded.'}</span><button className="btn btn-secondary" onClick={onBackToCatalogue}>Catalogue</button></div>

  const stageTitle = terminal ? 'Evidence report' : session.stage === 'diagnostic' ? `Case ${session.diagnostic_index + 1}${session.diagnostic_total ? ` of ${session.diagnostic_total}` : ''} — Baseline reasoning` : session.stage === 'apply' ? 'Unfamiliar Case — Application & Evaluation' : session.practice_active ? 'Guided practice — Support is recorded' : investigateMode === 'revision' ? 'Answer revision — Incorporating tutoring' : investigateMode === 'summary' ? 'Your diagnostic summary' : investigateMode === 'reference' ? 'Question and original answers' : 'Chat with your tutor'

  return <div className="session-page-wrapper">
    <div className="card session-topbar mb-4">
      <div className="session-topbar-header">
        <div className="session-title-group">
          <button type="button" className="btn btn-secondary btn-sm" onClick={onBackToCatalogue}>← Catalogue</button>
          <div>
            <h1 ref={headingRef} tabIndex={-1} className="session-concept-title">{session.concept_title || 'Concept Check'}</h1>
            <div className="session-stage-subtitle">{stageTitle}</div>
          </div>
        </div>
      </div>
      <div className="session-progress-wrapper">
        <StageProgressBar
          currentStage={session.stage}
          completedStages={completedStages}
          attemptedStages={attemptedStages}
          recordedStages={recordedStages}
        />
      </div>
    </div>

    {error && <div className="error-banner mb-4" role="alert"><span>{error}</span></div>}
    {resourceError && (
      <div className="error-banner mb-4" role="alert">
        <span>{resourceError}</span>
        <button type="button" className="btn btn-secondary btn-sm" onClick={() => setResourceError(null)}>Dismiss</button>
      </div>
    )}
    {submitting && <EvaluationProgressLoader />}
    {pending && !submitting && <div className="card recovery-card mb-4" role="status">
      <strong>Saved request awaiting confirmation</strong>
      <p>Retry resumes this exact request and preserves its original submission identifier.</p>
      <div className="action-wrap">
        <button type="button" className="btn btn-secondary" onClick={() => execute(pending)}>Retry saved request</button>
        {terminal && can('finish_session') && session.processing_status === 'failed' && <button type="button" className="btn btn-secondary" onClick={() => send('finish_session')}>Finish partial report</button>}
      </div>
    </div>}

    {!terminal && <div className="stage-content-container">
      {/* Stage: Diagnostic Baseline */}
      {session.stage === 'diagnostic' && (
        <div className="diagnostic-workspace">
          {prompt && <PromptView prompt={prompt} />}
          {session.messages && session.messages.filter(m => m.stage === 'diagnostic').length > 0 && (
            <div className="diagnostic-clarification-thread mb-3">
              <SessionTranscript
                messages={session.messages.filter(m => m.stage === 'diagnostic')}
                stage="diagnostic"
                onOpenResource={confirmResourceOpening}
                disabled={actionsDisabled || !can('resource_opened')}
              />
            </div>
          )}
          {can('clarify') && (
            <div className="diagnostic-clarify-bar mb-2">
              {!utility && (
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  disabled={actionsDisabled}
                  onClick={() => setUtility('clarify')}
                >
                  ❓ Ask a clarification question about the scenario
                </button>
              )}
            </div>
          )}
          {utility === 'clarify' ? (
            <div className="utility-composer-wrapper card p-3 mb-3">
              <div className="utility-composer-header mb-2">
                <strong>Ask about scenario assumptions</strong>
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  onClick={() => setUtility(null)}
                >
                  ✕ Cancel (return to answer)
                </button>
              </div>
              {composer(
                'clarify',
                'Question about the scenario assumptions',
                'Send clarification question',
                false,
                false
              )}
            </div>
          ) : (
            can('submit_answer') && composer('submit_answer', 'Explain what happens and why', 'Save baseline answer →', true)
          )}
        </div>
      )}

      {/* Stage: Investigate - Guided Practice Active */}
      {session.stage === 'investigate' && session.practice_active && (
        <div className="guided-practice-workspace">
          <div className="practice-header-card card mb-3">
            <span className="practice-header-badge">Guided practice · Supported learning</span>
            <h2 className="practice-title">Focused Practice Exercise</h2>
            <p className="muted-note">
              Practice is supported learning to help test your thinking. Submitting practice returns you to the tutoring conversation. It does not replace your baseline answer or count as an independent assessment.
            </p>
          </div>
          {prompt && <PromptView prompt={prompt} />}
          {session.messages && session.messages.length > 0 && (
            <details className="practice-transcript-details card p-2 mb-3">
              <summary className="text-sm text-muted">View tutoring conversation & practice guidance ({session.messages.length} messages)</summary>
              <div className="mt-2">
                <SessionTranscript
                  messages={session.messages}
                  stage="investigate"
                  onOpenResource={confirmResourceOpening}
                  disabled={actionsDisabled || !can('resource_opened')}
                />
              </div>
            </details>
          )}
          <div className="practice-help-controls-bar mb-2">
            {can('request_hint') && (
              <button
                type="button"
                className="btn btn-secondary btn-hint"
                disabled={actionsDisabled}
                onClick={() => send('request_hint')}
                title="Request a conceptual clue for this practice exercise"
              >
                💡 Give me a hint
              </button>
            )}
            {can('request_teaching') && (
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                disabled={actionsDisabled}
                onClick={() => send('request_teaching')}
              >
                📖 Explain concept
              </button>
            )}
            {can('clarify') && !utility && (
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                disabled={actionsDisabled}
                onClick={() => setUtility('clarify')}
              >
                ❓ Ask a question
              </button>
            )}
          </div>
          {utility === 'clarify' ? (
            <div className="utility-composer-wrapper card p-3 mb-3">
              <div className="utility-composer-header mb-2">
                <strong>Ask a practice question</strong>
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  onClick={() => setUtility(null)}
                >
                  ✕ Cancel (return to practice)
                </button>
              </div>
              {composer(
                'clarify',
                'Question about this practice exercise',
                'Send question',
                false,
                false
              )}
            </div>
          ) : (
            can('submit_practice') && (
              <div className="practice-composer-wrapper">
                {composer('submit_practice', 'Practice reasoning and justification', 'Submit guided practice →', true, true)}
              </div>
            )
          )}
        </div>
      )}

      {session.stage === 'investigate' && !session.practice_active && investigateMode === 'summary' && (
        <div className="diagnostic-review-workspace">
          <section className="card diagnostic-handoff">
            <h2>Your diagnostic is saved</h2>
            <p>Here is a first look at your answers. Next, talk through one question at a time with your tutor.</p>
            <button type="button" className="btn btn-primary" disabled={actionsDisabled} onClick={() => changeTutoringView('tutoring')}>Continue to tutor chat →</button>
            <p className="muted-note">AI feedback is provisional. You can clarify anything the tutor misunderstood.</p>
          </section>
          <DiagnosticFeedback
            attempts={session.attempts || []}
            conceptSlug={session.concept_slug}
            conceptTitle={session.concept_title}
            nextQuestion={firstTutorProbe || undefined}
            onRetryAssessment={can('retry_processing') ? () => { void send('retry_processing') } : undefined}
            disabled={actionsDisabled}
            onOpenResource={confirmResourceOpening}
          />

        </div>
      )}

      {session.stage === 'investigate' && !session.practice_active && investigateMode === 'reference' && (
        <div className="tutor-reference-workspace">
          <button type="button" className="btn btn-secondary tutor-return" onClick={() => changeTutoringView('tutoring')}>← Back to chat</button>
          <section className="contextual-reference-panel mb-3" aria-label="Question and original answers">
            <h2 className="contextual-reference-summary">Question and original answers</h2>
            <div className="contextual-reference-content p-3">
              {prompt && <PromptView prompt={prompt} />}
              {sourceAttempts.length > 0 && (
                <div className="mt-3">
                  <h4 className="text-sm font-semibold mb-2">Your original baseline answer:</h4>
                  {sourceAttempts.map(attempt => (
                    <div key={attempt.id} className="reference-answer">
                      <blockquote style={{ whiteSpace: 'pre-wrap' }}>{attempt.answer_text}</blockquote>
                      {attempt.diagram_preset && <PresetDiagramView diagram={attempt.diagram_preset} value={attempt.diagram_state || null} readOnly />}
                      {attempt.cloze_preset && <ClozeExerciseView cloze={attempt.cloze_preset} value={attempt.cloze_state as Record<string, string> | null} readOnly />}
                    </div>
                  ))}
                </div>
              )}
              {(session.evidence_cards || []).length > 0 && (
                <div className="mt-3">
                  <h4 className="text-sm font-semibold mb-2">Baseline diagnostic findings:</h4>
                  {(session.evidence_cards || []).map((card, index) => (
                    <div className="gap-finding-card mb-2" key={card.id || index}>
                      <strong>{card.title || card.gap_description || 'Possible concern to investigate'}</strong>
                      {card.evidence_quote && <blockquote>{card.evidence_quote}</blockquote>}
                      {card.probe_question && <p className="text-sm">Follow-up: {card.probe_question}</p>}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </section>

        </div>
      )}

      {/* Stage: Investigate - Dedicated Revision Workspace */}
      {session.stage === 'investigate' && !session.practice_active && investigateMode === 'revision' && (
        <div className="revision-workspace">
          <div className="revision-nav-bar mb-3">
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              onClick={() => changeTutoringView('tutoring')}
            >
              ← Return to tutoring conversation
            </button>
          </div>
          <div className="card revision-intro-card mb-3">
            <span className="scenario-label-badge">Revision Workspace</span>
            <h2>Review & Revise Your Baseline Answer</h2>
            <p className="muted-note">
              Incorporate what you explored with the tutor. Your draft is automatically saved in this browser tab even if you return to tutoring.
            </p>
          </div>
          {prompt && <PromptView prompt={prompt} />}
          {sourceAttempts.length > 0 && (
            <details className="earlier-answers-panel mb-3">
              <summary className="earlier-answers-summary">
                Review your original baseline answer
              </summary>
              <div className="attempts-stack">
                {sourceAttempts.map(attempt => (
                  <AttemptView key={attempt.id} attempt={attempt} anchor={false} />
                ))}
              </div>
            </details>
          )}
          {can('submit_answer') && (
            <div className="revision-composer-wrapper">
              {composer(
                'submit_answer',
                'Revised explanation of the original case',
                'Submit revised answer →',
                true,
                true
              )}
            </div>
          )}
          {can('continue') && (
            <details className="skip-revision-details mt-4">
              <summary className="text-sm text-muted">Prefer not to revise? Proceed directly to unfamiliar case</summary>
              <div className="skip-revision-content p-3 mt-1">
                <p className="muted-note">
                  Skipping revision means your original baseline answer remains the final evidence for this case. You will move directly to an independent unfamiliar transfer case.
                </p>
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  disabled={actionsDisabled}
                  onClick={() => send('continue')}
                >
                  Skip revision & attempt unfamiliar case →
                </button>
              </div>
            </details>
          )}
        </div>
      )}

      {/* Stage: Investigate - Primary Tutoring Workspace */}
      {session.stage === 'investigate' && !session.practice_active && investigateMode === 'tutoring' && (
        <div className="tutoring-workspace">
          <nav className="tutor-view-nav" aria-label="Tutoring workspace">
            <button type="button" className="btn btn-secondary btn-sm" disabled={actionsDisabled} onClick={() => changeTutoringView('summary')}>Review diagnostic</button>
            <button type="button" className="btn btn-secondary btn-sm" disabled={actionsDisabled} onClick={() => changeTutoringView('reference')}>View question</button>
          </nav>
          <div className="tutor-chat-surface">
          <div className="tutoring-chat-wrapper">
            <SessionTranscript
              messages={session.messages || []}
              stage={session.stage}
              focused
              onOpenResource={confirmResourceOpening}
              disabled={actionsDisabled || !can('resource_opened')}
            />
          </div>

          <div className="tutoring-composer-area mt-3">
            {session.messages && session.messages.length > 0 && (
              <div className="card revision-progression-banner mb-3" role="region" aria-label="Ready to revise">
                <div className="progression-callout-content">
                  <div className="progression-callout-text">
                    <h3 className="progression-callout-title">💡 Ready to update your answer?</h3>
                    <p className="muted-note">
                      You've explored this concept with your tutor. Take what you learned and revise your baseline explanation!
                    </p>
                  </div>
                  <button
                    type="button"
                    className="btn btn-primary"
                    disabled={actionsDisabled}
                    onClick={() => changeTutoringView('revision')}
                  >
                    Review and revise my answer →
                  </button>
                </div>
              </div>
            )}
            <div className="help-controls-bar mb-2">
              {can('request_hint') && (
                <button
                  type="button"
                  className="btn btn-secondary btn-hint"
                  disabled={actionsDisabled}
                  onClick={() => send('request_hint')}
                  title="Request a conceptual clue without revealing the answer"
                >
                  💡 Give me a hint
                </button>
              )}
              <HelpMenu
                canTeaching={can('request_teaching')}
                canPractice={can('request_practice')}
                canResource={can('request_help') || Boolean(session.concept_slug)}
                canClarify={can('clarify')}
                canCorrectAi={can('correct_ai')}
                disabled={actionsDisabled}
                onSelect={actionKey => {
                  if (actionKey === 'teaching') send('request_teaching')
                  else if (actionKey === 'practice') send('request_practice')
                  else if (actionKey === 'resource') {
                    if (session.concept_slug) openConceptGuide(`/v1/resources/${session.concept_slug}`)
                    else send('request_help')
                  }
                  else if (actionKey === 'clarify') setUtility('clarify')
                  else if (actionKey === 'correct_ai') setUtility('correct_ai')
                }}
              />
            </div>

            {utility && can(utility) ? (
              <div className="utility-composer-wrapper card p-3 mb-3">
                <div className="utility-composer-header mb-2">
                  <strong>{utility === 'clarify' ? 'Ask about the scenario assumptions' : 'Point out tutor misunderstanding'}</strong>
                  <button
                    type="button"
                    className="btn btn-secondary btn-sm"
                    onClick={() => setUtility(null)}
                  >
                    ✕ Cancel (return to chat)
                  </button>
                </div>
                {composer(
                  utility,
                  utility === 'clarify' ? 'Question about the scenario' : 'Correction of the AI’s interpretation',
                  utility === 'clarify' ? 'Send clarification question' : 'Send correction',
                  false,
                  false
                )}
              </div>
            ) : (
              can('answer_probe') && composer('answer_probe', 'Reply to the tutor', 'Send reply')
            )}
          </div>

          </div>
          {can('continue') && (
            <details className="skip-revision-details mt-3">
              <summary className="text-sm text-muted">Skip revision &amp; proceed to unfamiliar scenario</summary>
              <div className="skip-revision-content p-2 mt-1">
                <p className="muted-note">
                  Skipping revision leaves your initial baseline answer as the only evidence for the original case. You will move directly to an unfamiliar case challenge.
                </p>
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  disabled={actionsDisabled}
                  onClick={() => send('continue')}
                >
                  Skip revision &amp; proceed to unfamiliar case →
                </button>
              </div>
            </details>
          )}
        </div>
      )}

      {/* Stage: Apply - Unfamiliar Transfer Case */}
      {session.stage === 'apply' && (
        <div className="unfamiliar-case-workspace">
          <div className="unfamiliar-case-banner card mb-3">
            <div className="concept-focus-anchor mb-2">
              <span className="concept-focus-pill">Concept Focus: {session.concept_title || 'Backend Reasoning'}</span>
              <p className="concept-focus-note text-sm">
                Apply the core principles you explored in the earlier cases to this new scenario. Answer independently without hints.
              </p>
            </div>
            <span className="scenario-label-badge">Unfamiliar Transfer Case</span>
            <h2>Apply your understanding to a new scenario</h2>
            <p className="muted-note">
              This fresh scenario tests whether the principles transfer to an unfamiliar context. Answer independently without hints.
            </p>
          </div>
          {prompt && <PromptView prompt={prompt} />}
          {session.messages && session.messages.filter(m => m.stage === 'apply').length > 0 && (
            <div className="apply-clarification-thread mb-3">
              <SessionTranscript
                messages={session.messages.filter(m => m.stage === 'apply')}
                stage="apply"
                onOpenResource={confirmResourceOpening}
                disabled={actionsDisabled || !can('resource_opened')}
              />
            </div>
          )}
          {can('clarify') && (
            <div className="apply-clarify-bar mb-2">
              {!utility && (
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  disabled={actionsDisabled}
                  onClick={() => setUtility('clarify')}
                >
                  ❓ Ask a factual clarification question about this scenario
                </button>
              )}
            </div>
          )}
          {utility === 'clarify' ? (
            <div className="utility-composer-wrapper card p-3 mb-3">
              <div className="utility-composer-header mb-2">
                <strong>Ask a factual question about the scenario</strong>
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  onClick={() => setUtility(null)}
                >
                  ✕ Cancel (return to answer)
                </button>
              </div>
              <p className="muted-note">
                Only factual scenario clarification is provided during the transfer case; hints and coaching are not available.
              </p>
              {composer(
                'clarify',
                'Factual question about the scenario assumptions',
                'Send clarification question',
                false,
                false
              )}
            </div>
          ) : (
            can('submit_answer') && (
              <div className="apply-composer-wrapper">
                {composer(
                  'submit_answer',
                  'Explain what happens in this unfamiliar case and why',
                  'Submit unfamiliar case & view comparison report →',
                  true,
                  true
                )}
              </div>
            )
          )}
        </div>
      )}

      {/* Earlier Submitted Answers Accordion */}
      {(session.attempts || []).length > 0 && !(session.stage === 'investigate' && investigateMode === 'tutoring' && !session.practice_active) && (
        <details className="earlier-answers-panel mt-4">
          <summary className="earlier-answers-summary">
            All submitted answers in this session ({session.attempts?.length})
          </summary>
          <div className="attempts-stack mt-2">
            {session.attempts?.map(attempt => (
              <AttemptView key={attempt.id} attempt={attempt} />
            ))}
          </div>
        </details>
      )}

      {/* Quieter Finish Session Early Control */}
      {can('finish_session') && (
        <details className="quiet-finish-panel mt-4">
          <summary className="quiet-finish-summary text-sm text-muted">
            Finish session early…
          </summary>
          <div className="quiet-finish-content card p-3 mt-2">
            <h4>End session with partial evidence</h4>
            <p className="muted-note">
              You can finish now with the evidence collected so far. Any remaining steps (such as revising your answer or attempting the unfamiliar transfer case) will remain unassessed. Your report will accurately reflect that these steps were not attempted.
            </p>
            {pending && session.processing_status === 'failed' && (
              <p className="text-warning text-sm">
                Failed processing will stop. Your saved answer remains in the partial evidence report.
              </p>
            )}
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              disabled={submitting || (Boolean(pending) && session.processing_status !== 'failed')}
              onClick={() => send('finish_session')}
            >
              {pending && session.processing_status === 'failed'
                ? 'Finish partial report'
                : 'End session and view partial report'}
            </button>
          </div>
        </details>
      )}
    </div>}

    {terminal && (report ? <ReportView report={report} messages={session.messages || []} onBack={onBackToCatalogue} onOpenSession={onOpenSession} onRetryAssessments={can('retry_processing') ? () => { void send('retry_processing') } : undefined} retryDisabled={actionsDisabled} /> : <div className="card" role="status"><p>The saved report could not be loaded.</p><button className="btn btn-secondary" onClick={() => hydrate().catch(reason => setError(String(reason)))}>Reload report</button></div>)}
  </div>
}
