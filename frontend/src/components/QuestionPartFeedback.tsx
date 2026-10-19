import type { AttemptReport } from '../types'

const coverageLabels: Record<string, string> = {
  answered: 'Answered', partly_answered: 'Partly answered', partially_answered: 'Partly answered',
  unanswered: 'Unanswered', unclear: 'Unclear',
}
const issueLabels: Record<string, string> = {
  incorrect_claim: 'Incorrect claim', missing_requested_part: 'Missing requested part',
  ambiguous_wording: 'Needs clarification', ambiguous_wording_or_interpretation: 'Needs clarification',
  insufficient_evidence: 'Insufficient evidence', technical_failure: 'Assessment unavailable',
}

export function QuestionPartFeedback({ attempt, compact = false }: { attempt: AttemptReport; compact?: boolean }) {
  const parts = (attempt.question_parts || []).filter(part => !part.supplementary)
  if (!parts.length) return null
  const coverage = new Map((attempt.question_parts_coverage || []).map(row => [row.question_part_id, row]))
  return <section className="question-part-feedback" aria-label="Required question parts">
    <h4>Required question parts</h4>
    <ul className="question-part-list">
      {parts.map(part => {
        const id = part.id || part.part_id
        const row = id ? coverage.get(id) : undefined
        const label = row?.issue_type === 'technical_failure' ? undefined : coverageLabels[row?.coverage || '']
        const omitted = row?.coverage === 'unanswered'
        return <li key={id || part.description} className="card-flat question-part-card">
          <strong>{part.description}</strong> <span className="badge badge-coverage">{label || 'Coverage unavailable'}</span>
          {row?.issue_type && issueLabels[row.issue_type] && <span className="badge badge-warning">{issueLabels[row.issue_type]}</span>}
          {!compact && row?.demonstrated_explanation && <p><strong>What was correct:</strong> {row.demonstrated_explanation}</p>}
          {!compact && row?.explanation && <p><strong>Why this feedback:</strong> {row.explanation}</p>}
          {!label && !row?.explanation && <p className="muted-note">Coverage of this requested part could not be assessed.</p>}
          {!compact && row?.next_action && <p><strong>Next step:</strong> {row.next_action}</p>}
          {!compact && label && !omitted && row?.evidence?.trim() && <blockquote>{row.evidence}</blockquote>}
        </li>
      })}
    </ul>
  </section>
}
