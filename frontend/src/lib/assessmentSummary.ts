import type { AttemptReport, CriterionAssessment } from '../types'

export const evidenceLabels = {
  demonstrated: 'Demonstrated',
  partially_demonstrated: 'Partially demonstrated',
  not_addressed: 'Not addressed',
  ambiguous_needs_clarification: 'Needs clarification',
  technical_failure: 'Could not be assessed',
} as const

type EvidenceRating = keyof typeof evidenceLabels

export interface AttributedCriterion extends CriterionAssessment {
  attempt_id?: string
  case_number?: number
  case_type?: string
  scenario_text?: string
}

export function groupCriteria(attempts: AttemptReport[]): Record<EvidenceRating, AttributedCriterion[]> {
  const groups: Record<EvidenceRating, AttributedCriterion[]> = {
    demonstrated: [], partially_demonstrated: [], not_addressed: [], ambiguous_needs_clarification: [], technical_failure: [],
  }
  attempts.forEach((attempt, attemptIndex) => {
    const rawCriteria = attempt.criteria || (attempt as unknown as { criterion_assessments?: CriterionAssessment[] }).criterion_assessments || []
    const conceptual = rawCriteria.filter(c => !c.skill_id?.startsWith('exercise:'))
    for (const criterion of conceptual) {
      const rating = criterion.rating as EvidenceRating
      const consistent = rating === 'demonstrated' ? criterion.met === true
        : ['partially_demonstrated', 'not_addressed'].includes(rating) ? criterion.met === false : criterion.met === null
      const rubricList = (attempt as unknown as { case_snapshot?: { rubric?: { criteria?: Array<{ id: string; label: string }> } } }).case_snapshot?.rubric?.criteria
      const rubricMatch = rubricList?.find(c => c.id === (criterion as unknown as { criterion_id?: string }).criterion_id)
      const label = criterion.criterion || rubricMatch?.label || (criterion as unknown as { label?: string }).label || 'Criterion'
      const evidence = criterion.evidence || (criterion as unknown as { evidence_quote?: string }).evidence_quote || ''
      groups[rating in groups && consistent ? rating : 'technical_failure'].push({
        ...criterion,
        criterion: label,
        evidence,
        attempt_id: attempt.id,
        case_number: attemptIndex + 1,
        case_type: attempt.case_type || (attempt as unknown as { case_snapshot?: { case_type?: string } }).case_snapshot?.case_type,
        scenario_text: attempt.scenario_text || (attempt as unknown as { case_snapshot?: { scenario_text?: string } }).case_snapshot?.scenario_text,
      })
    }
    const missing = Math.max(0, (attempt.total_criteria_count ?? conceptual.length) - conceptual.length)
    if (missing || !conceptual.length) groups.technical_failure.push({
      criterion: missing ? `${missing} prepared criterion assessment(s) are missing.` : 'Assessment of this saved answer is not available.',
      met: null, rating: 'technical_failure', status: 'provisional',
      attempt_id: attempt.id,
      case_number: attemptIndex + 1,
      case_type: attempt.case_type,
      scenario_text: attempt.scenario_text,
    })
  })
  return groups
}
