import React, { useId } from 'react'
import type { DictationMode } from '../lib/dictation'

export const TranscriptReview: React.FC<{
  existingText: string; transcript: string; rawTranscript: string
  onChange: (text: string) => void; onConfirm: (mode: DictationMode) => void
  onCancel: () => void; onRecordAgain: () => void
}> = ({ existingText, transcript, rawTranscript, onChange, onConfirm, onCancel, onRecordAgain }) => {
  const id = useId()
  const hasAnswer = Boolean(existingText.trim())
  return <section aria-label="Review the new recording">
    <label htmlFor={id}>Review and edit this recording’s transcript</label>
    <textarea id={id} aria-label="Review and edit transcript" className="textarea" rows={4} maxLength={30000}
      value={transcript} onChange={event => onChange(event.target.value)} />
    {rawTranscript !== transcript && <p className="muted-note">Edited from this recording’s raw transcription.</p>}
    <p className="muted-note">{hasAnswer ? 'Add this recording to the end of your existing answer. Replacement is a separate choice.' : 'Use this transcript to start your answer.'} You can edit the combined answer before submitting it.</p>
    <div className="action-wrap">
      <button type="button" className="btn btn-secondary btn-sm" onClick={onCancel}>Cancel</button>
      <button type="button" className="btn btn-secondary btn-sm" onClick={onRecordAgain}>Record this clip again</button>
      {hasAnswer && <button type="button" className="btn btn-secondary btn-sm" disabled={!transcript.trim()} onClick={() => onConfirm('replace')}>Replace my answer</button>}
      <button type="button" className="btn btn-primary btn-sm" disabled={!transcript.trim()} onClick={() => onConfirm('append')}>{hasAnswer ? 'Add to my answer' : 'Use this transcript'}</button>
    </div>
  </section>
}
