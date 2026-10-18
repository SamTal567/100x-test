import React, { useState } from 'react'
import type { AttemptReport } from '../types'

interface DiagnosticFeedbackProps {
  attempts: AttemptReport[]
  conceptSlug?: string
  conceptTitle?: string
  onScrollToChat?: () => void
}

export const DiagnosticFeedback: React.FC<DiagnosticFeedbackProps> = ({
  attempts,
  conceptSlug,
  conceptTitle,
  onScrollToChat,
}) => {
  const [sourcesDismissed, setSourcesDismissed] = useState(false)
  const baselineAttempts = attempts.filter(a => a.stage === 'diagnostic')
  if (!baselineAttempts.length) return null

  // Collect conceptual criteria across baseline attempts
  const allCriteria = baselineAttempts.flatMap(a =>
    a.criteria.filter(c => !c.skill_id?.startsWith('exercise:'))
  )
  const demonstrated = allCriteria.filter(c => c.met === true)
  const needsAttention = allCriteria.filter(c => c.met !== true)
  const total = allCriteria.length
  const scorePercent = total > 0 ? Math.round((demonstrated.length / total) * 100) : 0
  const isPerfect = total > 0 && demonstrated.length === total

  const resourceUrl = conceptSlug ? `/v1/resources/${conceptSlug}` : null

  return (
    <section className="diagnostic-feedback-wrapper mb-4" aria-label="Diagnostic Feedback and Optional Sources">
      {/* 1. Baseline Performance Feedback */}
      <div className="card mb-3" style={{ borderLeft: `4px solid ${isPerfect ? 'var(--mint, #10b981)' : '#f59e0b'}` }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.5rem' }}>
          <div>
            <h3 style={{ margin: 0, fontSize: '1.1rem' }}>
              Baseline Diagnostic Results
            </h3>
            <p className="muted-note" style={{ margin: '0.25rem 0 0 0' }}>
              Here is what was identified in your initial explanation:
            </p>
          </div>
          <div style={{ textAlign: 'right' }}>
            <span style={{ fontSize: '1.25rem', fontWeight: 'bold' }}>
              {scorePercent}%
            </span>
            <span className="muted-note" style={{ display: 'block', fontSize: '0.75rem' }}>
              {demonstrated.length}/{total} criteria demonstrated
            </span>
          </div>
        </div>

        <div style={{ marginTop: '0.75rem', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '0.75rem' }}>
          {/* Demonstrated / What was right */}
          <div className="card-flat" style={{ padding: '0.75rem', background: 'var(--bg-surface-alt)' }}>
            <strong style={{ color: 'var(--mint, #10b981)', fontSize: '0.85rem' }}>
              ✓ What You Got Right ({demonstrated.length})
            </strong>
            {demonstrated.length > 0 ? (
              <ul style={{ margin: '0.5rem 0 0 0', paddingLeft: '1.2rem', fontSize: '0.85rem' }}>
                {demonstrated.map((c, i) => (
                  <li key={i} style={{ marginBottom: '0.25rem' }}>{c.criterion}</li>
                ))}
              </ul>
            ) : (
              <p className="muted-note" style={{ margin: '0.5rem 0 0 0', fontSize: '0.8rem' }}>
                None of the core criteria were clearly demonstrated in the baseline attempt.
              </p>
            )}
          </div>

          {/* Missing / What was wrong / needs attention */}
          <div className="card-flat" style={{ padding: '0.75rem', background: 'var(--bg-surface-alt)' }}>
            <strong style={{ color: '#f59e0b', fontSize: '0.85rem' }}>
              ⚠️ Missing or Needs Attention ({needsAttention.length})
            </strong>
            {needsAttention.length > 0 ? (
              <ul style={{ margin: '0.5rem 0 0 0', paddingLeft: '1.2rem', fontSize: '0.85rem' }}>
                {needsAttention.map((c, i) => (
                  <li key={i} style={{ marginBottom: '0.25rem' }}>
                    <strong>{c.criterion}</strong>: {c.rating?.replaceAll('_', ' ') || 'needs clarification'}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="muted-note" style={{ margin: '0.5rem 0 0 0', fontSize: '0.8rem' }}>
                All prepared criteria were satisfied in your baseline answers!
              </p>
            )}
          </div>
        </div>
      </div>

      {/* 2. Optional Concept Sources Guide */}
      {resourceUrl && !sourcesDismissed && (
        <div className="card recovery-card mb-3" style={{ background: 'var(--bg-surface-alt)' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.5rem' }}>
            <div>
              <span className="badge badge-reviewed" style={{ marginBottom: '0.25rem' }}>
                Optional Resource Guide
              </span>
              <h4 style={{ margin: '0.25rem 0', fontSize: '1rem' }}>
                📖 {conceptTitle || 'Concept'} Reference Guide
              </h4>
              <p className="muted-note" style={{ margin: 0, fontSize: '0.85rem' }}>
                {isPerfect
                  ? 'You demonstrated all baseline criteria! Reading this lesson is optional. You can review it or jump straight into the AI chat.'
                  : 'You missed some key concepts. We recommend taking 2 minutes to skim this curated lesson guide before chatting with the AI.'}
              </p>
            </div>
            <div className="action-wrap" style={{ marginTop: '0.5rem' }}>
              <a
                href={resourceUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="btn btn-secondary btn-sm"
              >
                📖 Open Study Guide
              </a>
              <button
                type="button"
                className="btn btn-primary btn-sm"
                onClick={onScrollToChat || (() => setSourcesDismissed(true))}
              >
                💬 Continue to AI Chat ↓
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  )
}
