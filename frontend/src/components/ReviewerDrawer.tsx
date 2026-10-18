import React, { useState, useEffect, useCallback, useRef } from 'react'
import { api } from '../api/client'
import { PresetDiagramView } from './PresetDiagramView'
import { ClozeExerciseView } from './ClozeExerciseView'
import type { AssessmentReviewItem, CaseReviewItem } from '../types'

interface ReviewerDrawerProps {
  isOpen: boolean
  onClose: () => void
  onReviewSubmitted?: () => void
}

export const ReviewerDrawer: React.FC<ReviewerDrawerProps> = ({
  isOpen,
  onClose,
  onReviewSubmitted,
}) => {
  const [reviewerKey, setReviewerKey] = useState('')
  const dialogRef = useRef<HTMLDialogElement>(null)
  const [assessments, setAssessments] = useState<AssessmentReviewItem[]>([])
  const [cases, setCases] = useState<CaseReviewItem[]>([])
  const [mode, setMode] = useState<'assessments' | 'cases'>('assessments')
  const [reviewerName, setReviewerName] = useState('')
  const [caseNotes, setCaseNotes] = useState<Record<string, string>>({})
  const [loading, setLoading] = useState(false)
  const [submittingId, setSubmittingId] = useState<string | null>(null)
  const [editNotes, setEditNotes] = useState<Record<string, string>>({})
  const [editMet, setEditMet] = useState<Record<string, boolean | null>>({})
  const [errorMsg, setErrorMsg] = useState<string | null>(null)

  const loadAssessments = useCallback(async (keyToUse: string) => {
    if (!keyToUse.trim()) return
    setLoading(true)
    setErrorMsg(null)
    try {
      const [data, caseData] = await Promise.all([api.listReviewAssessments(keyToUse), api.listReviewCases(keyToUse)])
      setAssessments(data)
      setCases(caseData)
      const initialMet: Record<string, boolean | null> = {}
      const initialNotes: Record<string, string> = {}
      data.forEach((item) => {
        initialMet[item.id] = item.met
        initialNotes[item.id] = item.reviewer_notes || ''
      })
      setEditMet(initialMet)
      setEditNotes(initialNotes)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err)
      setErrorMsg(`Authorization failed or server error: ${msg}`)
      setAssessments([])
      setCases([])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (isOpen && !dialogRef.current?.open) dialogRef.current?.showModal()
  }, [isOpen])

  const handleSubmitReview = async (id: string, isCorrection = false) => {
    setSubmittingId(id)
    try {
      await api.submitReview(
        id,
        {
          status: isCorrection ? 'corrected' : 'reviewed',
          met: editMet[id],
          reviewer_notes: editNotes[id] || undefined,
          reviewer_name: reviewerName.trim(),
        },
        reviewerKey
      )
      setAssessments(await api.listReviewAssessments(reviewerKey))
      onReviewSubmitted?.()
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err)
      setErrorMsg(`Review submission failed: ${msg}`)
    } finally {
      setSubmittingId(null)
    }
  }

  const handleCaseReview = async (id: string, status: 'reviewed' | 'rejected') => {
    if (!reviewerName.trim()) return
    setSubmittingId(id)
    setErrorMsg(null)
    try {
      await api.submitCaseReview(id, { review_status: status, reviewer_name: reviewerName.trim(), reviewer_notes: caseNotes[id] || undefined }, reviewerKey)
      setCases(await api.listReviewCases(reviewerKey))
      onReviewSubmitted?.()
    } catch (reason) { setErrorMsg(`Case review failed: ${reason instanceof Error ? reason.message : String(reason)}`) }
    finally { setSubmittingId(null) }
  }

  if (!isOpen) return null

  return (
    <dialog
      ref={dialogRef}
      className="drawer-backdrop"
      onCancel={onClose}
      aria-labelledby="reviewer-drawer-title"
    >
      <div
        className="drawer-panel"
        style={{ width: '600px', maxWidth: '95vw' }}
      >
        <div className="drawer-header">
          <div>
            <h2 id="reviewer-drawer-title" style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--text-primary)' }}>
              🛡️ Assessment Reviewer Desk
            </h2>
            <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
              Server-authenticated human verification with full attempt context
            </div>
          </div>
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            onClick={onClose}
            aria-label="Close Reviewer Desk"
          >
            ✕ Close
          </button>
        </div>

        <div className="drawer-body">
          {/* Reviewer Auth Key Input */}
          <div className="card-flat mb-3" style={{ padding: '12px', background: 'var(--bg-subtle, #f8fafc)' }}>
            <label htmlFor="reviewer-auth-key" style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, marginBottom: '6px' }}>
              🔑 Reviewer Authorization Key (Required):
            </label>
            <div style={{ display: 'flex', gap: '8px' }}>
              <input
                id="reviewer-auth-key"
                type="password"
                className="input"
                value={reviewerKey}
                autoComplete="off"
                onChange={(e) => setReviewerKey(e.target.value)}
                placeholder="Enter server reviewer secret..."
                style={{ fontSize: '0.85rem' }}
              />
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={() => loadAssessments(reviewerKey)}
                disabled={loading || !reviewerKey.trim()}
              >
                Authenticate
              </button>
            </div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '4px' }}>
              Enter the staff credential for this visit. It is held only in memory and cleared when the desk closes.
            </div>
            <label htmlFor="reviewer-name" className="muted-note">Reviewer name for attributed decisions</label>
            <input id="reviewer-name" className="input" value={reviewerName} onChange={event => setReviewerName(event.target.value)} autoComplete="name" placeholder="Your name" />
          </div>

          <div className="action-wrap" aria-label="Review category"><button type="button" className={`btn btn-sm ${mode === 'assessments' ? 'btn-primary' : 'btn-secondary'}`} aria-pressed={mode === 'assessments'} onClick={() => setMode('assessments')}>Learner evidence</button><button type="button" className={`btn btn-sm ${mode === 'cases' ? 'btn-primary' : 'btn-secondary'}`} aria-pressed={mode === 'cases'} onClick={() => setMode('cases')}>Authored cases and rubrics</button></div>

          {loading && (
            <div className="loading-container">
              <div className="spinner" />
              <span>Verifying authorization and loading assessments...</span>
            </div>
          )}

          {errorMsg && (
            <div className="error-banner mb-3" role="alert">
              <span>⚠️ {errorMsg}</span>
            </div>
          )}

          {mode === 'assessments' && !loading && assessments.length === 0 && !errorMsg && reviewerKey && (
            <div className="empty-state">
              <div className="empty-icon">✓</div>
              <h3>No assessments awaiting review</h3>
              <p>All submitted criteria have either been verified or none have been submitted yet.</p>
            </div>
          )}

          {mode === 'assessments' && !loading && assessments.length > 0 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                Showing <strong>{assessments.length}</strong> criterion judgments with full answer context:
              </div>

              {assessments.map((item) => (
                <div key={item.id} className="card" style={{ padding: '16px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                    <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
                      <span className={`badge ${item.status === 'provisional' ? 'badge-provisional' : 'badge-reviewed'}`}>
                        {item.status.toUpperCase()}
                      </span>
                      {item.skill_id && (
                        <span style={{ fontSize: '11px', fontWeight: 600, padding: '2px 6px', background: '#e0e7ff', color: '#3730a3', borderRadius: '4px' }}>
                          Skill: {item.skill_id}
                        </span>
                      )}
                    </div>
                    <span style={{ fontSize: '0.75rem', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
                      Rating: {item.rating || 'not recorded'}
                    </span>
                  </div>

                  <div style={{ fontWeight: 700, fontSize: '0.95rem', color: 'var(--text-primary)', marginBottom: '8px' }}>
                    {item.criterion}
                  </div>

                  {/* Scenario context */}
                  {item.scenario_text && (
                    <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '6px' }}>
                      <strong>Scenario:</strong> {item.scenario_text}
                    </div>
                  )}

                  {/* Learner Answer */}
                  {item.answer_text && (
                    <div style={{
                      fontSize: '0.85rem',
                      background: 'var(--input-bg, #f1f5f9)',
                      borderLeft: '3px solid var(--color-primary, #2563eb)',
                      padding: '8px 12px',
                      borderRadius: '4px',
                      marginBottom: '8px',
                      color: 'var(--text-primary, #0f172a)',
                    }}>
                      <strong>Learner Answer:</strong> "{item.answer_text}"
                    </div>
                  )}

                  {/* Diagram State if present */}
                  {item.diagram_preset && <PresetDiagramView diagram={item.diagram_preset} value={item.diagram_state} readOnly />}
                  {item.cloze_preset && <ClozeExerciseView cloze={item.cloze_preset} value={item.cloze_state as Record<string, string> | null} readOnly />}
                  <p className="muted-note">Case version {item.case_version ?? 'not recorded'} · Rubric version {item.rubric_version ?? 'not recorded'}</p>

                  {/* Expected Reference Answer */}
                  {item.reference_answer && (
                    <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '8px' }}>
                      <strong>Reference Standard:</strong> {item.reference_answer}
                    </div>
                  )}

                  {/* Proposed Evidence Quote */}
                  {item.evidence && (
                    <div style={{
                      fontSize: '0.8rem',
                      fontStyle: 'italic',
                      color: '#475569',
                      marginBottom: '10px',
                      padding: '4px 8px',
                      background: '#f8fafc',
                      borderRadius: '4px',
                    }}>
                      Proposed Evidence: "{item.evidence}"
                    </div>
                  )}
                  {item.proposal && <details><summary>Original model proposal</summary><p>Rating: {item.proposal.rating?.replaceAll('_', ' ') || 'Not recorded'}</p><p>Evidence: {item.proposal.evidence || 'None recorded'}</p></details>}
                  {Boolean(item.review_history?.length) && <details><summary>Attributed review history</summary><ol className="support-history">{item.review_history?.map((revision, index) => <li key={index}><strong>{revision.reviewer_name || 'Authorized reviewer'}</strong>{revision.created_at && ` · ${new Date(revision.created_at).toLocaleString()}`}<p>{revision.review?.status} · {revision.review?.rating?.replaceAll('_', ' ')}</p><p>{revision.review?.reviewer_notes}</p></li>)}</ol></details>}

                  <div style={{ marginBottom: '10px' }}>
                    <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, marginBottom: '6px' }}>
                      Human Evaluator Verdict:
                    </label>
                    <div style={{ display: 'flex', gap: '8px' }}>
                      <button
                        type="button"
                        className={`btn btn-sm ${editMet[item.id] === true ? 'btn-accent-mint' : 'btn-secondary'}`}
                        onClick={() => setEditMet(prev => ({ ...prev, [item.id]: true }))}
                      >
                        ✓ Met
                      </button>
                      <button
                        type="button"
                        className={`btn btn-sm ${editMet[item.id] === false ? 'btn-accent-peach' : 'btn-secondary'}`}
                        onClick={() => setEditMet(prev => ({ ...prev, [item.id]: false }))}
                      >
                        ✗ Not Met
                      </button>
                      <button
                        type="button"
                        className={`btn btn-sm ${editMet[item.id] === null ? 'btn-primary' : 'btn-secondary'}`}
                        onClick={() => setEditMet(prev => ({ ...prev, [item.id]: null }))}
                      >
                        ? Unclear
                      </button>
                    </div>
                  </div>

                  <div style={{ marginBottom: '10px' }}>
                    <input
                      aria-label={`Reviewer rationale for ${item.criterion}`}
                      type="text"
                      className="input"
                      placeholder="Add reviewer rationale/correction notes..."
                      value={editNotes[item.id] || ''}
                      onChange={(e) => setEditNotes(prev => ({ ...prev, [item.id]: e.target.value }))}
                      style={{ fontSize: '0.85rem', padding: '6px 10px' }}
                    />
                  </div>

                  <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
                    <button
                      type="button"
                      className="btn btn-secondary btn-sm"
                      disabled={submittingId === item.id || !reviewerName.trim()}
                      onClick={() => handleSubmitReview(item.id, true)}
                    >
                      Correct & Save
                    </button>
                    <button
                      type="button"
                      className="btn btn-primary btn-sm"
                      disabled={submittingId === item.id || !reviewerName.trim()}
                      onClick={() => handleSubmitReview(item.id, false)}
                    >
                      {submittingId === item.id ? 'Saving...' : 'Confirm as Reviewed'}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
          {mode === 'cases' && !loading && <div className="attempts-stack">
            <p className="muted-note">Inspect assumptions, alternative reasoning, objective exercise choices and matched skill criteria before marking a case reviewed. Learners never receive this private reference.</p>
            {cases.map(item => <details className="card" style={{ padding: '16px' }} key={item.id}><summary><strong>{item.authored_id || item.case_type}</strong> · v{item.version} · {item.review_status}{!item.active && ' · historical'}</summary><p style={{ whiteSpace: 'pre-wrap' }}>{item.scenario_text}</p><ul className="support-history">{item.assumptions?.map((assumption, index) => <li key={index}>{assumption}</li>)}</ul>
              {item.diagram_preset && <PresetDiagramView diagram={item.diagram_preset} readOnly />}
              {item.cloze_preset && <ClozeExerciseView cloze={item.cloze_preset} readOnly />}
              <h3>Private expected reasoning</h3><p style={{ whiteSpace: 'pre-wrap' }}>{item.reference_answer}</p><h3>Rubric version {item.rubric_version}</h3><ul className="support-history">{item.criteria.map((criterion, index) => <li key={index}>{String(criterion.criterion || criterion.text || criterion.description || 'Prepared criterion')}{criterion.skill_id && ` · ${criterion.skill_id}`}</li>)}</ul>
              <label htmlFor={`case-note-${item.id}`}>Case review rationale</label><textarea id={`case-note-${item.id}`} className="textarea" rows={2} value={caseNotes[item.id] || ''} onChange={event => setCaseNotes(previous => ({ ...previous, [item.id]: event.target.value }))} />
              <div className="action-wrap"><button className="btn btn-secondary btn-sm" disabled={!item.active || !reviewerName.trim() || submittingId === item.id} onClick={() => handleCaseReview(item.id, 'rejected')}>Reject for revision</button><button className="btn btn-primary btn-sm" disabled={!item.active || !reviewerName.trim() || submittingId === item.id} onClick={() => handleCaseReview(item.id, 'reviewed')}>Mark case reviewed</button></div>
            </details>)}
          </div>}
        </div>
      </div>
    </dialog>
  )
}
