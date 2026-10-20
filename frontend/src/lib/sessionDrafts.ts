import type { TranscriptionSegment, TurnRequest } from '../types'

export interface AnswerDraft {
  text: string
  diagram: Record<string, unknown> | null
  cloze: Record<string, string> | null
  inputMode: 'typed' | 'voice'
  transcriptionId: string | null
  transcriptionSegments?: TranscriptionSegment[]
}

export const emptyDraft: AnswerDraft = { text: '', diagram: null, cloze: null, inputMode: 'typed', transcriptionId: null, transcriptionSegments: [] }
export const draftKey = (sessionId: string, promptId: string | undefined, action: string) =>
  `cc:draft:${sessionId}:${promptId || 'none'}:${action}`
export const pendingKey = (sessionId: string) => `cc:pending:${sessionId}`

export function readStored<T>(key: string): T | null {
  try { return JSON.parse(sessionStorage.getItem(key) || 'null') as T | null } catch { return null }
}

export function writeStored(key: string, value: unknown): void {
  try {
    if (value === null) sessionStorage.removeItem(key)
    else sessionStorage.setItem(key, JSON.stringify(value))
  } catch { /* Browser storage can be unavailable; in-memory editing remains usable. */ }
}

export function savedPending(sessionId: string): TurnRequest | null {
  const candidate = readStored<TurnRequest>(pendingKey(sessionId))
  return candidate?.client_turn_id && candidate.action ? candidate : null
}

export function supportLabel(support?: string | null): string {
  const labels: Record<string, string> = {
    independent: 'Independent response', after_clarification: 'After scenario clarification',
    after_hint: 'After a hint', after_teaching: 'After teaching', after_practice: 'After guided practice',
    after_follow_up: 'After a targeted follow-up', after_help_offered: 'After help was offered',
    after_help_unknown: 'After tutoring (type not recorded)',
    after_resource: 'After opening or completing a study guide',
    legacy_unknown: 'Historical support not recorded', unknown: 'Support not recorded',
  }
  if (!support) return 'Support not recorded'
  return labels[support] || support.replaceAll('_', ' ')
}

// Local authored resources and explicitly curated documentation domains only.
export function safeResourceUrl(raw: string): string | null {
  if (/^\/v1\/resources\/[a-zA-Z0-9_-]+(?:#[\w-]+)?$/.test(raw)) return raw
  try {
    const url = new URL(raw)
    if (url.protocol !== 'https:' || url.username || url.password) return null
    return ['developer.mozilla.org', 'www.postgresql.org', 'www.sqlite.org', 'sqlite.org'].includes(url.hostname) ? url.href : null
  } catch { return null }
}
