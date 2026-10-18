import React from 'react'
import { evidenceLabels, groupCriteria } from '../lib/assessmentSummary'
import { TrackedResourceLink } from './TrackedResourceLink'
import type { ResourceOpening } from './TrackedResourceLink'
import type { AttemptReport } from '../types'

interface DiagnosticFeedbackProps {
  attempts: AttemptReport[]
  conceptSlug?: string
  conceptTitle?: string
  onScrollToChat?: () => void
  onRetryAssessment?: () => void
  disabled?: boolean
  onOpenResource?: ResourceOpening
}

export const DiagnosticFeedback: React.FC<DiagnosticFeedbackProps> = ({
  attempts, conceptSlug, conceptTitle, onScrollToChat, onRetryAssessment, disabled, onOpenResource,
}) => {
  const baseline = attempts.filter(a => a.stage === 'diagnostic')
  if (!baseline.length) return null
  const groups = groupCriteria(baseline)
  return <section className="diagnostic-feedback-wrapper mb-4" aria-label="Baseline feedback and optional guide">
    <div className="card mb-3">
      <h3>Baseline evidence</h3>
      <p className="muted-note">These judgments describe your submitted answers. AI judgments remain provisional until human review. An omission needs a follow-up before it is treated as a misconception.</p>
      <div className="comparison-columns">
        {Object.entries(groups).filter(([, rows]) => rows.length).map(([rating, rows]) => <div className="card-flat" key={rating}>
          <h4>{evidenceLabels[rating as keyof typeof evidenceLabels]} ({rows.length})</h4>
          {rating === 'technical_failure' && <p className="muted-note">Processing did not provide a usable judgment. This is not evidence of a wrong answer.</p>}
          <ul>{rows.map((criterion, index) => <li key={index}>{criterion.criterion}</li>)}</ul>
        </div>)}
      </div>
      {groups.technical_failure.length > 0 && onRetryAssessment && <button type="button" className="btn btn-secondary btn-sm" disabled={disabled} onClick={onRetryAssessment}>Retry unavailable assessments</button>}
    </div>
    {conceptSlug && <div className="card recovery-card mb-3">
      <h4>{conceptTitle || 'Concept'} reference guide</h4>
      <p className="muted-note">Reading is optional. You can answer the tutor’s follow-up first. Reading a lesson is support, and opening a guide does not prove learning.</p>
      <div className="action-wrap">
        <TrackedResourceLink url={`/v1/resources/${conceptSlug}`} onOpenResource={onOpenResource} disabled={disabled}>Open Study Guide</TrackedResourceLink>
        <button type="button" className="btn btn-primary btn-sm" onClick={onScrollToChat}>Continue to AI Chat ↓</button>
      </div>
    </div>}
  </section>
}
