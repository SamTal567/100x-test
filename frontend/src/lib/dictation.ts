import type { AnswerDraft } from './sessionDrafts'
import type { TranscriptionSegment } from '../types'

export type DictationMode = 'append' | 'replace'

export function editDraftText(draft: AnswerDraft, text: string): AnswerDraft {
  return text.trim() ? { ...draft, text }
    : { ...draft, text, inputMode: 'typed', transcriptionId: null, transcriptionSegments: [] }
}

export function applyDictation(draft: AnswerDraft, transcript: string, transcriptionId: string, mode: DictationMode = 'append'): AnswerDraft {
  const clip = transcript.trim()
  if (!clip || !transcriptionId) throw new Error('Review a nonempty transcript before adding it.')
  const prior: TranscriptionSegment[] = !draft.text.trim() ? [] : draft.transcriptionSegments?.length ? draft.transcriptionSegments
    : draft.inputMode === 'voice' && draft.transcriptionId ? [{ transcription_id: draft.transcriptionId,
      confirmed_text: draft.text, confirmation_scope: 'legacy_draft' }] : []
  if (mode === 'append' && prior.some(segment => segment.transcription_id === transcriptionId)) return draft
  const text = mode === 'replace' || !draft.text.trim() ? clip : `${draft.text}\n\n${clip}`
  const segments: TranscriptionSegment[] = [...(mode === 'replace' ? [] : prior),
    { transcription_id: transcriptionId, confirmed_text: clip, confirmation_scope: 'clip' }]
  if (text.length > 30000) throw new Error('The combined answer is too long. Shorten the answer or transcript before adding it.')
  if (segments.length > 20) throw new Error('An answer can include up to 20 recordings. Review or replace the answer before adding another.')
  return { ...draft, text, inputMode: 'voice', transcriptionId, transcriptionSegments: segments }
}
