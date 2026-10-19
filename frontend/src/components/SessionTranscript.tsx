import React from 'react'
import { MessageContent } from './MessageContent'
import type { Message, SessionDetail } from '../types'
import type { ResourceOpening } from './TrackedResourceLink'

export const SessionTranscript: React.FC<{ messages: Message[]; stage: SessionDetail['stage']; onOpenResource?: ResourceOpening; disabled?: boolean; open?: boolean }> = ({ messages, stage, onOpenResource, disabled, open = false }) => {
  if (!messages.length) return null
  const terminal = stage === 'review' || stage === 'completed'
  const isInvestigate = stage === 'investigate'

  const diagnosticMessages = isInvestigate ? messages.filter(m => m.stage === 'diagnostic') : []
  const activeMessages = isInvestigate && diagnosticMessages.length > 0 ? messages.filter(m => m.stage !== 'diagnostic') : messages

  const renderMessage = (message: Message) => <div key={message.id} className={`chat-message message-${message.role}`}>
    <div className="message-role-label">{message.role === 'learner' ? 'You' : message.role === 'tutor' ? 'Tutor' : 'Session'}</div>
    <MessageContent content={message.content} onOpenResource={onOpenResource} disabled={disabled} />
    {message.provider_status === 'error' && <p className="provider-failure" role="status">AI provider request failed. This message is not a successful model assessment.</p>}
    {message.provider_status === 'unavailable' && <p className="provider-failure">AI provider unavailable. Any local guidance is labelled development support.</p>}
  </div>

  const conversation = <section className="card chat-section" aria-label="Saved conversation">
    <div className="chat-header-row">
      <h2 className="chat-title">{stage === 'investigate' || terminal ? 'Tutoring and clarification conversation' : 'Scenario clarifications'}</h2>
      {isInvestigate && <span className="chat-hint-note">Discussing your reasoning with the tutor</span>}
    </div>
    {diagnosticMessages.length > 0 && <details className="diagnostic-history-panel mb-3" open={open}>
      <summary className="diagnostic-history-summary">Earlier diagnostic submissions ({diagnosticMessages.length})</summary>
      <div className="chat-messages diagnostic-history-list mt-2">
        {diagnosticMessages.map(renderMessage)}
      </div>
    </details>}
    <div className="chat-messages" aria-live={terminal ? 'off' : 'polite'}>
      {activeMessages.map(renderMessage)}
    </div>
  </section>
  return terminal ? <details className="saved-transcript earlier-session" open={open}><summary>Saved tutoring and clarification conversation</summary>{conversation}</details> : conversation
}
