import React from 'react'
import { safeResourceUrl } from '../lib/sessionDrafts'

const InlineContent: React.FC<{ text: string }> = ({ text }) => <>
  {text.split(/(\[[^\]\n]+\]\([^\s)]+\))/g).map((part, index) => {
    const match = part.match(/^\[([^\]]+)\]\(([^)]+)\)$/)
    const href = match && safeResourceUrl(match[2])
    return href && match ? <a key={index} href={href} target="_blank" rel="noopener noreferrer">{match[1]}</a> : <React.Fragment key={index}>{part}</React.Fragment>
  })}
</>

export const MessageContent: React.FC<{ content: string }> = ({ content }) => <div className="message-text">
  {content.split(/(```[^\n]*\n[\s\S]*?```)/g).map((part, index) => part.startsWith('```')
    ? <pre key={index} className="ascii-diagram-container"><code>{part.replace(/^```[^\n]*\n/, '').replace(/```$/, '')}</code></pre>
    : <span key={index} style={{ whiteSpace: 'pre-wrap' }}><InlineContent text={part} /></span>)}
</div>
