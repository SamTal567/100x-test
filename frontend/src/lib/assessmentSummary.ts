import type { AttemptReport, CriterionAssessment } from '../types'

export const evidenceLabels = {
  demonstrated: 'Demonstrated',
  partially_demonstrated: 'Partially demonstrated',
  not_addressed: 'Not addressed',
  ambiguous_needs_clarification: 'Needs clarification',
  technical_failure: 'Could not be assessed',
} as const

type EvidenceRating = keyof typeof evidenceLabels

export function groupCriteria(attempts: AttemptReport[]): Record<EvidenceRating, CriterionAssessment[]> {
  const groups: Record<EvidenceRating, CriterionAssessment[]> = {
    demonstrated: [], partially_demonstrated: [], not_addressed: [], ambiguous_needs_clarification: [], technical_failure: [],
  }
  for (const attempt of attempts) {
    const conceptual = attempt.criteria.filter(c => !c.skill_id?.startsWith('exercise:'))
    for (const criterion of conceptual) {
      const rating = criterion.rating as EvidenceRating
      const consistent = rating === 'demonstrated' ? criterion.met === true
        : ['partially_demonstrated', 'not_addressed'].includes(rating) ? criterion.met === false : criterion.met === null
      groups[rating in groups && consistent ? rating : 'technical_failure'].push(criterion)
    }
    const missing = Math.max(0, (attempt.total_criteria_count ?? conceptual.length) - conceptual.length)
    if (missing || !conceptual.length) groups.technical_failure.push({
      criterion: missing ? `${missing} prepared criterion assessment(s) are missing.` : 'Assessment of this saved answer is not available.',
      met: null, rating: 'technical_failure', status: 'provisional',
    })
  }
  return groups
}
