import React from 'react'
import { MessageContent } from './MessageContent'
import type { Message, SessionDetail } from '../types'

export const SessionTranscript: React.FC<{ messages: Message[]; stage: SessionDetail['stage'] }> = ({ messages, stage }) => {
  if (!messages.length) return null
  const terminal = stage === 'review' || stage === 'completed'
  const conversation = <section className="card chat-section" aria-label="Saved conversation">
    <h2 className="chat-title">{stage === 'investigate' || terminal ? 'Tutoring and clarification conversation' : 'Scenario clarifications'}</h2>
    <div className="chat-messages" aria-live={terminal ? 'off' : 'polite'}>{messages.map(message => <div key={message.id} className={`chat-message message-${message.role}`}>
      <div className="message-role-label">{message.role === 'learner' ? 'You' : message.role === 'tutor' ? 'Tutor' : 'Session'}</div>
      <MessageContent content={message.content} />
      {message.provider_status === 'error' && <p className="provider-failure" role="status">AI provider request failed. This message is not a successful model assessment.</p>}
      {message.provider_status === 'unavailable' && <p className="provider-failure">AI provider unavailable. Any local guidance is labelled development support.</p>}
    </div>)}</div>
  </section>
  return terminal ? <details className="saved-transcript earlier-session"><summary>Saved tutoring and clarification conversation</summary>{conversation}</details> : conversation
}
