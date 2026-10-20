import type { AttemptReport, EvidenceCard, Message, SessionReport } from '../types'

export interface TutorFocus {
  quote: string | null
  question: string | null
}

export function getTutorFocus(cards: EvidenceCard[], attempts: AttemptReport[], promptId?: string): TutorFocus | null {
  if (!promptId) return null
  for (const card of cards) {
    const source = attempts.find(attempt => attempt.id === card.source_attempt_id && attempt.case_prompt_id === promptId)
    if (!source) continue
    const proposed = card.evidence_quote?.trim() || ''
    const answer = source.answer_text || ''
    const offset = proposed ? answer.toLowerCase().indexOf(proposed.toLowerCase()) : -1
    const exact = offset >= 0 ? answer.slice(offset, offset + proposed.length) : ''
    // Display the learner's own casing. Unmatched/legacy model text is not a quote.
    const quote = exact && exact.toLowerCase() === proposed.toLowerCase() ? exact : null
    return { quote, question: card.probe_question || null }
  }
  return null
}

export function reportStageEvidence(report: SessionReport, messages?: Message[]) {
  const answerRow = (label: string, stage: string, empty: string) => {
    const attempts = report.attempts.filter(attempt => attempt.stage === stage && !['practice', 'guided_practice'].includes(attempt.case_type))
    if (!attempts.length) return { label, detail: `${empty} · Not attempted / unassessed` }
    const criteria = attempts.flatMap(attempt => attempt.criteria || []).filter(criterion => !criterion.skill_id?.startsWith('exercise:'))
    const valid = criteria.filter(criterion => criterion.met != null && criterion.rating !== 'technical_failure' && criterion.issue_type !== 'technical_failure')
    const complete = attempts.every(attempt => !attempt.processing_status || attempt.processing_status === 'complete')
    const assessment = !valid.length ? 'Assessment unavailable'
      : !complete || valid.length !== criteria.length ? 'Assessment partly available'
        : 'Assessed against prepared criteria'
    return { label, detail: `${attempts.length === 1 ? 'Answer submitted' : `${attempts.length} answers submitted`} · ${assessment}` }
  }
  const tutoring = messages?.filter(message => message.stage === 'investigate')
  const hasReply = tutoring?.some(message => message.role === 'learner')
  const hasQuestion = tutoring?.some(message => message.role === 'tutor')
  const hasHelp = report.interventions_used?.some(item => item.opened || item.completed || item.status === 'delivered')
  const tutoringDetail = hasReply ? 'Learner reply recorded'
    : hasQuestion ? 'Follow-up offered; no learner reply recorded'
      : hasHelp ? 'Help recorded; no learner reply recorded'
        : messages === undefined ? 'Conversation history unavailable'
          : 'No tutoring conversation recorded'
  return [
    answerRow('Baseline diagnostic', 'diagnostic', 'No baseline answer submitted'),
    { label: 'Tutor conversation', detail: tutoringDetail },
    answerRow('Supported revision', 'investigate', 'No revised answer submitted'),
    answerRow('Fresh scenario', 'apply', 'No fresh-case answer submitted'),
  ]
}
