import React from 'react'
import { safeResourceUrl } from '../lib/sessionDrafts'
import { TrackedResourceLink } from './TrackedResourceLink'
import type { ResourceOpening } from './TrackedResourceLink'

const InlineContent: React.FC<{ text: string; onOpenResource?: ResourceOpening; disabled?: boolean }> = ({ text, onOpenResource, disabled }) => <>
  {text.split(/(\[[^\]\n]+\]\([^\s)]+\))/g).map((part, index) => {
    const match = part.match(/^\[([^\]]+)\]\(([^)]+)\)$/)
    const href = match && safeResourceUrl(match[2])
    return href && match ? onOpenResource
      ? <TrackedResourceLink key={index} url={href} onOpenResource={onOpenResource} disabled={disabled}>{match[1]}</TrackedResourceLink>
      : <a key={index} href={href} target="_blank" rel="noopener noreferrer">{match[1]}</a>
      : <React.Fragment key={index}>{part}</React.Fragment>
  })}
</>

export const MessageContent: React.FC<{ content: string; onOpenResource?: ResourceOpening; disabled?: boolean }> = ({ content, onOpenResource, disabled }) => <div className="message-text">
  {content.split(/(```[^\n]*\n[\s\S]*?```)/g).map((part, index) => part.startsWith('```')
    ? <pre key={index} className="ascii-diagram-container"><code>{part.replace(/^```[^\n]*\n/, '').replace(/```$/, '')}</code></pre>
    : <span key={index} style={{ whiteSpace: 'pre-wrap' }}><InlineContent text={part} onOpenResource={onOpenResource} disabled={disabled} /></span>)}
</div>
