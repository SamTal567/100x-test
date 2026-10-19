import React from 'react'
import { evidenceLabels, groupCriteria } from '../lib/assessmentSummary'
import { TrackedResourceLink } from './TrackedResourceLink'
import { QuestionPartFeedback } from './QuestionPartFeedback'
import type { ResourceOpening } from './TrackedResourceLink'
import type { AttemptReport } from '../types'

interface DiagnosticFeedbackProps {
  attempts: AttemptReport[]
  conceptSlug?: string
  conceptTitle?: string
  nextQuestion?: string
  onRetryAssessment?: () => void
  disabled?: boolean
  onOpenResource?: ResourceOpening
}

export const DiagnosticFeedback: React.FC<DiagnosticFeedbackProps> = ({
  attempts, conceptSlug, conceptTitle, nextQuestion, onRetryAssessment, disabled, onOpenResource,
}) => {
  const baseline = attempts.filter(a => a.stage === 'diagnostic')
  if (!baseline.length) return null
  const groups = groupCriteria(baseline)

  const demonstratedNames = [...new Set(groups.demonstrated.map(c => c.criterion))]
  const clarificationNames = [
    ...new Set([
      ...groups.ambiguous_needs_clarification.map(c => c.criterion),
      ...groups.partially_demonstrated.map(c => c.criterion),
      ...groups.not_addressed.map(c => c.criterion),
    ]),
  ]
  const technicalFailures = groups.technical_failure

  return <section className="diagnostic-summary-card card mb-4" aria-label="Diagnostic summary">
    <div className="diagnostic-summary-header">
      <h3 className="diagnostic-summary-title">What your diagnostic answers showed</h3>
      <span className="badge badge-provisional">Provisional baseline</span>
    </div>

    <div className="diagnostic-summary-body">
      {demonstratedNames.length > 0 && <div className="diagnostic-summary-item">
        <span className="diagnostic-item-badge badge-demonstrated">✓ Demonstrated</span>
        <p className="diagnostic-item-text">{demonstratedNames.slice(0, 3).join(' · ')}{demonstratedNames.length > 3 ? ` · ${demonstratedNames.length - 3} more in details` : ''}</p>
      </div>}

      {clarificationNames.length > 0 && <div className="diagnostic-summary-item">
        <span className="diagnostic-item-badge badge-clarification">? Needs clarification</span>
        <p className="diagnostic-item-text">{clarificationNames.slice(0, 3).join(' · ')}{clarificationNames.length > 3 ? ` · ${clarificationNames.length - 3} more in details` : ''}</p>
      </div>}

      {nextQuestion && <div className="diagnostic-summary-item next-focus-item">
        <span className="diagnostic-item-badge badge-next">Next tutor question</span>
        <p className="diagnostic-item-text">{nextQuestion}</p>
      </div>}

      {technicalFailures.length > 0 && <div className="diagnostic-summary-item failure-item">
        <span className="diagnostic-item-badge badge-failure">Assessment notice</span>
        <p className="diagnostic-item-text">{technicalFailures.length} criterion assessment(s) could not be evaluated by the provider.</p>
      </div>}
    </div>

    <details className="diagnostic-details-accordion">
      <summary className="diagnostic-details-toggle">View diagnostic details (per-answer evidence)</summary>
      <div className="diagnostic-details-content mt-3">
    {baseline.some(attempt => attempt.question_parts?.some(part => !part.supplementary)) && <div className="diagnostic-part-feedback">
      {baseline.map((attempt, index) => <div key={attempt.id || index}>
        <h4>Case {index + 1}</h4>
        <QuestionPartFeedback attempt={attempt} />
      </div>)}
    </div>}

        <p className="muted-note">Detailed baseline criteria across your submitted answers. Distinctions between answers are preserved below.</p>
        <div className="comparison-columns">
          {Object.entries(groups).filter(([, rows]) => rows.length).map(([rating, rows]) => <div className="card-flat" key={rating}>
            <h4>{evidenceLabels[rating as keyof typeof evidenceLabels]} ({rows.length})</h4>
            {rating === 'technical_failure' && <p className="muted-note">Processing did not provide a usable judgment. This is not evidence of a wrong answer.</p>}
            <ul>{rows.map((criterion, index) => <li key={index} className="diagnostic-criterion-row">
              {criterion.case_number ? <span className="case-attribution-badge">Case {criterion.case_number}: </span> : null}
              <span className="diagnostic-criterion-name">{criterion.criterion}</span>
              {criterion.demonstrated_explanation && <p><strong>What was correct:</strong> {criterion.demonstrated_explanation}</p>}
              {criterion.explanation && <p><strong>Why this rating:</strong> {criterion.explanation}</p>}
              {criterion.next_action && <p><strong>Next step:</strong> {criterion.next_action}</p>}
              {criterion.evidence && !['not_addressed', 'technical_failure'].includes(criterion.rating || '') && criterion.issue_type !== 'technical_failure' && criterion.coverage !== 'unanswered' && <span className="criterion-evidence-inline"> — “{criterion.evidence}”</span>}
            </li>)}</ul>
          </div>)}
        </div>
        {groups.technical_failure.length > 0 && onRetryAssessment && <div className="mt-3"><button type="button" className="btn btn-secondary btn-sm" disabled={disabled} onClick={onRetryAssessment}>Retry unavailable assessments</button></div>}
      </div>
    </details>

    {conceptSlug && onOpenResource && <div className="diagnostic-guide-note mt-2">
      <span className="muted-note">Optional reading: </span>
      <TrackedResourceLink url={`/v1/resources/${conceptSlug}`} onOpenResource={onOpenResource} disabled={disabled}>Open {conceptTitle || 'concept'} reference guide</TrackedResourceLink>
    </div>}
  </section>
}
