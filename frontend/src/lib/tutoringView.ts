import type { Message } from '../types'

export type TutoringView = 'summary' | 'tutoring' | 'reference' | 'revision'
export const tutoringViewKey = (sessionId: string) => `cc:tutoring-view:${sessionId}`

export function initialTutoringView(saved: unknown, messages: Pick<Message, 'stage' | 'role'>[]): TutoringView {
  if (saved === 'summary' || saved === 'tutoring' || saved === 'reference' || saved === 'revision') return saved
  return messages.some(message => message.stage === 'investigate' && message.role === 'learner') ? 'tutoring' : 'summary'
}
