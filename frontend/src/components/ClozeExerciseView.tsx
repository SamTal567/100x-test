import React from 'react'
import type { ClozePreset } from '../types'

interface ClozeExerciseViewProps {
  cloze: ClozePreset
  value?: Record<string, string> | null
  onChange?: (state: Record<string, string>) => void
  readOnly?: boolean
}

export const ClozeExerciseView: React.FC<ClozeExerciseViewProps> = ({
  cloze,
  value = {},
  onChange,
  readOnly = false,
}) => {
  const selections = value || {}

  const handleSelect = (blankId: string, option: string) => {
    if (readOnly || !onChange) return
    onChange({
      ...selections,
      [blankId]: option,
    })
  }

  // Parse sentence_template into chunks and blanks
  // e.g. "When carts live only in {blank1}, redeploying the server {blank2} because process memory is {blank3}."
  const parts = cloze.sentence_template.split(/(\{[^{}]+\})/)

  return (
    <div
      className="cloze-exercise-card"
      style={{
        border: '1.5px solid var(--border-color, #cbd5e1)',
        borderRadius: '12px',
        padding: '16px',
        background: 'var(--surface-color, #ffffff)',
        marginTop: '12px',
        marginBottom: '16px',
        boxShadow: '0 2px 4px rgba(0,0,0,0.04)',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '10px' }}>
        <span
          style={{
            fontSize: '11px',
            fontWeight: 700,
            textTransform: 'uppercase',
            letterSpacing: '0.05em',
            padding: '2px 8px',
            borderRadius: '999px',
            background: '#fef3c7',
            color: '#92400e',
          }}
        >
          Cloze Practice Exercise
        </span>
        <span style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-primary, #0f172a)' }}>
          Complete the conceptual statement
        </span>
      </div>

      <div
        style={{
          fontSize: '14px',
          lineHeight: '2',
          color: 'var(--text-primary, #1e293b)',
          padding: '12px 14px',
          background: 'var(--bg-subtle, #f8fafc)',
          borderRadius: '8px',
          border: '1px solid var(--border-subtle, #e2e8f0)',
          marginBottom: '14px',
        }}
      >
        {parts.map((part, index) => {
          const match = part.match(/^\{([^{}]+)\}$/)
          if (match) {
            const blankId = match[1]
            const blankDef = cloze.blanks.find((b) => b.id === blankId)
            const currentChoice = selections[blankId] || ''

            return (
              <span key={index} style={{ margin: '0 4px', display: 'inline-block' }}>
                <select
                  aria-label={`Complete blank ${blankId}`}
                  value={currentChoice}
                  disabled={readOnly}
                  onChange={(e) => handleSelect(blankId, e.target.value)}
                  style={{
                    padding: '4px 8px',
                    borderRadius: '6px',
                    border: currentChoice ? '2px solid #2563eb' : '2px dashed #94a3b8',
                    background: currentChoice ? '#eff6ff' : '#ffffff',
                    color: currentChoice ? '#1d4ed8' : '#64748b',
                    fontWeight: 600,
                    fontSize: '13px',
                    cursor: readOnly ? 'default' : 'pointer',
                  }}
                >
                  <option value="">[ Select Option ]</option>
                  {blankDef?.options.map((opt) => (
                    <option key={opt} value={opt}>
                      {opt}
                    </option>
                  ))}
                </select>
              </span>
            )
          }
          return <span key={index}>{part}</span>
        })}
      </div>

      <div style={{ fontSize: '12.5px', color: 'var(--text-secondary, #475569)', fontStyle: 'italic' }}>
        💡 {cloze.justification_prompt}
      </div>
    </div>
  )
}
