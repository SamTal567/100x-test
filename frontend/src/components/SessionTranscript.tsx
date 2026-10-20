import React, { useEffect, useRef } from 'react'
import { MessageContent } from './MessageContent'
import type { Message, SessionDetail } from '../types'
import type { ResourceOpening } from './TrackedResourceLink'
import type { TutorFocus } from '../lib/learningEvidence'

export const SessionTranscript: React.FC<{ messages: Message[]; stage: SessionDetail['stage']; onOpenResource?: ResourceOpening; disabled?: boolean; open?: boolean; focused?: boolean; focus?: TutorFocus | null }> = ({ messages, stage, onOpenResource, disabled, open = false, focused = false, focus }) => {
  const messagesRef = useRef<HTMLDivElement>(null)
  const followLatest = useRef(true)
  useEffect(() => {
    if (focused && followLatest.current && messagesRef.current) {
      messagesRef.current.scrollTop = messagesRef.current.scrollHeight
    }
  }, [focused, messages.length])
  if (!messages.length) return null
  const terminal = stage === 'review' || stage === 'completed'
  const isInvestigate = stage === 'investigate'

  const diagnosticMessages = isInvestigate ? messages.filter(m => m.stage === 'diagnostic') : []
  const activeMessages = isInvestigate && diagnosticMessages.length > 0 ? messages.filter(m => m.stage !== 'diagnostic') : messages
  // The paired question remains visible in the focus card; its stored message
  // still appears in full transcripts and reports.
  const firstMessage = activeMessages[0]
  const visibleMessages = focused && focus?.question && firstMessage?.role === 'tutor' && firstMessage.content === focus.question
    && (!firstMessage.provider_status || firstMessage.provider_status === 'complete') ? activeMessages.slice(1) : activeMessages

  const renderMessage = (message: Message) => <div key={message.id} className={`chat-message message-${message.role}`}>
    <div className="message-role-label">{message.role === 'learner' ? 'You' : message.role === 'tutor' ? 'Tutor' : 'Session'}</div>
    <MessageContent content={message.content} onOpenResource={onOpenResource} disabled={disabled} />
    {message.provider_status === 'error' && <p className="provider-failure" role="status">AI provider request failed. This message is not a successful model assessment.</p>}
    {message.provider_status === 'unavailable' && <p className="provider-failure">AI provider unavailable. Any local guidance is labelled development support.</p>}
  </div>

  const conversation = <section className={`card chat-section${focused ? ' focused-chat' : ''}`} aria-label={focused ? 'Tutor conversation' : 'Saved conversation'}>
    <div className="chat-header-row">
      <h2 className="chat-title">{focused ? 'Chat with your tutor' : stage === 'investigate' || terminal ? 'Tutoring and clarification conversation' : 'Scenario clarifications'}</h2>
      {isInvestigate && <span className="chat-hint-note">{focused ? 'Reply to the question below. Ask for a hint whenever you need one.' : 'Discussing your reasoning with the tutor'}</span>}
    </div>
    {focused && focus && <section className="tutor-focus" aria-label="Reasoning being investigated">
      {focus.quote ? <><h3>Sentence we’re checking</h3><blockquote>{focus.quote}</blockquote></>
        : <p className="muted-note">No specific sentence was quoted. The tutor is asking you to clarify your reasoning.</p>}
      <p className="muted-note">This is a point to investigate, not a confirmed misconception.</p>
      {focus.question && <div className="tutor-focus-question"><strong>Initial follow-up</strong><MessageContent content={focus.question} onOpenResource={onOpenResource} disabled={disabled} /></div>}
    </section>}
    {!focused && diagnosticMessages.length > 0 && <details className="diagnostic-history-panel mb-3" open={open}>
      <summary className="diagnostic-history-summary">Earlier diagnostic submissions ({diagnosticMessages.length})</summary>
      <div className="chat-messages diagnostic-history-list mt-2">
        {diagnosticMessages.map(renderMessage)}
      </div>
    </details>}
    <div ref={messagesRef} className="chat-messages" tabIndex={focused ? 0 : undefined} aria-label={focused ? 'Tutoring messages' : undefined} aria-live={terminal ? 'off' : 'polite'} onScroll={event => {
      const node = event.currentTarget
      followLatest.current = node.scrollHeight - node.scrollTop - node.clientHeight < 64
    }}>
      {visibleMessages.map(renderMessage)}
    </div>
  </section>
  return terminal ? <details className="saved-transcript earlier-session" open={open}><summary>Saved tutoring and clarification conversation</summary>{conversation}</details> : conversation
}
