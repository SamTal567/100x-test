import React from 'react'
import { safeResourceUrl } from '../lib/sessionDrafts'
import { TrackedResourceLink } from './TrackedResourceLink'
import type { ResourceOpening } from './TrackedResourceLink'

const renderFormattedText = (raw: string, keyPrefix: string | number) => {
  return raw.split(/(`[^`\n]+`|\*\*(?:[^\n*]|\*(?!\*))+?\*\*)/g).map((token, i) => {
    const key = `${keyPrefix}-${i}`
    if (token.startsWith('`') && token.endsWith('`') && token.length >= 2) {
      return <code key={key}>{token.slice(1, -1)}</code>
    }
    if (token.startsWith('**') && token.endsWith('**') && token.length >= 4) {
      return <strong key={key}>{token.slice(2, -2)}</strong>
    }
    return token
  })
}

const InlineContent: React.FC<{ text: string; onOpenResource?: ResourceOpening; disabled?: boolean }> = ({ text, onOpenResource, disabled }) => <>
  {text.split(/(\[[^\]\n]+\]\([^\s)]+\))/g).map((part, index) => {
    const match = part.match(/^\[([^\]]+)\]\(([^)]+)\)$/)
    const href = match && safeResourceUrl(match[2])
    return href && match ? onOpenResource
      ? <TrackedResourceLink key={index} url={href} onOpenResource={onOpenResource} disabled={disabled}>{renderFormattedText(match[1], `link-${index}`)}</TrackedResourceLink>
      : <a key={index} href={href} target="_blank" rel="noopener noreferrer">{renderFormattedText(match[1], `link-${index}`)}</a>
      : <React.Fragment key={index}>{renderFormattedText(part, index)}</React.Fragment>
  })}
</>

export const MessageContent: React.FC<{ content: string; onOpenResource?: ResourceOpening; disabled?: boolean }> = ({ content, onOpenResource, disabled }) => <div className="message-text">
  {content.split(/(```[^\n]*\n[\s\S]*?```)/g).map((part, index) => part.startsWith('```')
    ? <pre key={index} className="ascii-diagram-container"><code>{part.replace(/^```[^\n]*\n/, '').replace(/```$/, '')}</code></pre>
    : <span key={index} style={{ whiteSpace: 'pre-wrap' }}><InlineContent text={part} onOpenResource={onOpenResource} disabled={disabled} /></span>)}
</div>
