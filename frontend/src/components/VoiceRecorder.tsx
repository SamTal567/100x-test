import React, { useState, useRef, useEffect } from 'react'
import { api } from '../api/client'
import { TranscriptReview } from './TranscriptReview'
import type { DictationMode } from '../lib/dictation'
import { transcriptionDraft } from '../lib/dictation'

interface VoiceRecorderProps {
  sessionId: string
  existingText: string
  onConfirmedTranscript: (text: string, transcriptionId: string, mode: DictationMode) => void
  onCancel: () => void
}

export const VoiceRecorder: React.FC<VoiceRecorderProps> = ({
  sessionId,
  existingText,
  onConfirmedTranscript,
  onCancel,
}) => {
  const [recordingState, setRecordingState] = useState<'idle' | 'recording' | 'transcribing' | 'reviewing'>('idle')
  const [seconds, setSeconds] = useState(0)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)
  const [rawTranscript, setRawTranscript] = useState('')
  const [editedTranscript, setEditedTranscript] = useState('')
  const [transcriptionId, setTranscriptionId] = useState<string | null>(null)

  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<Blob[]>([])
  const timerRef = useRef<number | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const mountedRef = useRef(true)
  const confirmedRef = useRef(false)

  useEffect(() => {
    mountedRef.current = true
    return () => {
      mountedRef.current = false
      if (timerRef.current) clearInterval(timerRef.current)
      const recorder = mediaRecorderRef.current
      if (recorder) {
        recorder.onstop = null
        recorder.ondataavailable = null
        if (recorder.state === 'recording') recorder.stop()
      }
      streamRef.current?.getTracks().forEach(track => track.stop())
      chunksRef.current = []
    }
  }, [])

  const startRecording = async () => {
    setErrorMsg(null)
    confirmedRef.current = false
    chunksRef.current = []
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      if (!mountedRef.current) { stream.getTracks().forEach(track => track.stop()); return }
      streamRef.current = stream
      const mimeType = MediaRecorder.isTypeSupported('audio/webm') ? 'audio/webm' : 'audio/mp4'
      const mediaRecorder = new MediaRecorder(stream, { mimeType })
      mediaRecorderRef.current = mediaRecorder

      mediaRecorder.ondataavailable = (e) => {
        if (e.data && e.data.size > 0) {
          chunksRef.current.push(e.data)
        }
      }

      mediaRecorder.onstop = async () => {
        stream.getTracks().forEach(track => track.stop())
        if (!mountedRef.current) return
        const audioBlob = new Blob(chunksRef.current, { type: mimeType })
        await handleTranscribe(audioBlob)
      }

      mediaRecorder.start(250)
      setRecordingState('recording')
      setSeconds(0)

      timerRef.current = window.setInterval(() => {
        setSeconds(prev => prev + 1)
      }, 1000)
    } catch (err: unknown) {
      streamRef.current?.getTracks().forEach(track => track.stop())
      if (!mountedRef.current) return
      const msg = err instanceof Error ? err.message : String(err)
      setErrorMsg(`Microphone access failed: ${msg}. You can type your answer instead.`)
      setRecordingState('idle')
    }
  }

  const stopRecording = () => {
    if (timerRef.current) {
      clearInterval(timerRef.current)
      timerRef.current = null
    }
    if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
      mediaRecorderRef.current.stop()
      setRecordingState('transcribing')
    }
  }

  const handleTranscribe = async (blob: Blob) => {
    try {
      setRecordingState('transcribing')
      const result = await api.uploadTranscription(sessionId, blob, blob.type.includes('mp4') ? 'audio.mp4' : 'audio.webm')
      if (!mountedRef.current) return
      if (result.status === 'failed' || !result.raw_transcript) throw new Error('No usable transcript was returned')
      setTranscriptionId(result.id)
      const draft = transcriptionDraft(result)
      setRawTranscript(draft.rawTranscript)
      setEditedTranscript(draft.editableTranscript)
      setRecordingState('reviewing')
    } catch (err: unknown) {
      if (!mountedRef.current) return
      const msg = err instanceof Error ? err.message : String(err)
      setErrorMsg(`Transcription unavailable: ${msg}. You can continue by typing your answer.`)
      setRecordingState('idle')
    }
  }

  const handleConfirm = (mode: DictationMode) => {
    if (confirmedRef.current) return
    if (!editedTranscript.trim() || !transcriptionId) {
      setErrorMsg('Transcript cannot be empty.')
      return
    }
    try {
      confirmedRef.current = true
      onConfirmedTranscript(editedTranscript.trim(), transcriptionId, mode)
    } catch (error) {
      confirmedRef.current = false
      setErrorMsg(error instanceof Error ? error.message : 'The transcript could not be added. Your existing answer is preserved.')
    }
  }

  return (
    <div className="voice-panel">
      <div className="voice-status" role="status" aria-live="polite">
        {recordingState === 'recording' && (
          <>
            <span className="recording-indicator" />
            <span style={{ fontWeight: 600, color: 'var(--color-error)' }}>
              Recording... {Math.floor(seconds / 60)}:{String(seconds % 60).padStart(2, '0')}
            </span>
          </>
        )}
        {recordingState === 'transcribing' && (
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '8px' }}>
            <span className="spinner" style={{ width: '16px', height: '16px', borderWidth: '2px' }} />
            <span>Transcribing audio with Fish Audio...</span>
          </span>
        )}
        {recordingState === 'idle' && (
          <span style={{ fontSize: '0.9rem', color: 'var(--text-secondary)' }}>
            🎙️ {existingText.trim() ? 'Record more to add to your existing answer.' : 'Dictate your response.'} Review and edit the new transcript before using it.
          </span>
        )}
        {recordingState === 'reviewing' && (
          <span style={{ fontSize: '0.9rem', fontWeight: 600, color: 'var(--color-success)' }}>
            ✓ Transcription complete. Review and edit your words below:
          </span>
        )}
      </div>

      {errorMsg && (
        <div className="error-banner" style={{ fontSize: '0.85rem', padding: '8px 12px' }}>
          <span>⚠️ {errorMsg}</span>
        </div>
      )}

      {recordingState === 'reviewing' && <TranscriptReview existingText={existingText} transcript={editedTranscript} rawTranscript={rawTranscript}
        onChange={setEditedTranscript} onConfirm={handleConfirm} onCancel={onCancel}
        onRecordAgain={() => { setErrorMsg(null); setRecordingState('idle') }} />}

      <div style={{ display: 'flex', gap: '10px', marginTop: '12px', justifyContent: 'flex-end' }}>
        {recordingState === 'idle' && (
          <>
            <button type="button" className="btn btn-secondary btn-sm" onClick={onCancel}>
              Cancel
            </button>
            <button type="button" className="btn btn-accent-peach btn-sm" onClick={startRecording}>
              🎙️ Start Recording
            </button>
          </>
        )}

        {recordingState === 'recording' && (
          <><button type="button" className="btn btn-secondary btn-sm" onClick={onCancel}>Cancel recording</button><button type="button" className="btn btn-primary btn-sm" onClick={stopRecording}>
            ⏹️ Stop & Transcribe
          </button></>
        )}

        {recordingState === 'transcribing' && <button type="button" className="btn btn-secondary btn-sm" onClick={onCancel}>Cancel transcription</button>}
      </div>
    </div>
  )
}
