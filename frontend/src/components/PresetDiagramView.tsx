import React, { useId } from 'react'
import type { PresetDiagram } from '../types'

interface PresetDiagramViewProps {
  diagram: PresetDiagram
  value?: Record<string, unknown> | null
  onChange?: (state: Record<string, unknown>) => void
  readOnly?: boolean
}

export const PresetDiagramView: React.FC<PresetDiagramViewProps> = ({
  diagram,
  value,
  onChange,
  readOnly = false,
}) => {
  const diagramUid = useId().replace(/:/g, '')
  const selectedRepair = String(value?.repair_selection || value?.selected_repair || value?.selected_target || '')
  const legacyBlank = (value?.selected_blank as string) || ''
  const blankSelections = (value?.blanks || {}) as Record<string, string>
  const repairTarget = diagram.repair_options?.find(option => option.id === selectedRepair)?.target_node

  const handleRepairChange = (optionId: string) => {
    if (readOnly || !onChange) return
    onChange({
      ...value,
      repair_selection: optionId,
    })
  }

  const handleBlankChange = (blankId: string, choice: string) => {
    if (readOnly || !onChange) return
    onChange({
      ...value,
      blanks: { ...blankSelections, [blankId]: choice },
    })
  }

  // Node styles by type
  const getNodeColor = (type: string) => {
    switch (type) {
      case 'actor':
        return { bg: '#eef2ff', border: '#4f46e5', text: '#312e81' }
      case 'process':
        return { bg: '#f0f9ff', border: '#0284c7', text: '#0c4a6e' }
      case 'volatile':
        return { bg: '#fffbeb', border: '#d97706', text: '#78350f' }
      case 'persistent':
        return { bg: '#f0fdf4', border: '#16a34a', text: '#14532d' }
      case 'blank':
        return { bg: '#f8fafc', border: '#94a3b8', text: '#475569' }
      default:
        return { bg: '#ffffff', border: '#64748b', text: '#1e293b' }
    }
  }

  return (
    <div
      className="preset-diagram-card"
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
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span
            style={{
              fontSize: '11px',
              fontWeight: 700,
              textTransform: 'uppercase',
              letterSpacing: '0.05em',
              padding: '2px 8px',
              borderRadius: '999px',
              background: '#e0e7ff',
              color: '#3730a3',
            }}
          >
            Structured Diagram Exercise
          </span>
          <span style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-primary, #0f172a)' }}>
            {diagram.title}
          </span>
        </div>
        <span style={{ fontSize: '12px', color: 'var(--text-muted, #64748b)' }}>
          Mode: {diagram.interaction_type}
        </span>
      </div>

      <p style={{ fontSize: '13px', color: 'var(--text-secondary, #334155)', margin: '0 0 12px 0' }}>
        {diagram.task_instruction}
      </p>

      {/* SVG Canvas */}
      <div
        style={{
          width: '100%',
          overflowX: 'auto',
          background: 'var(--bg-subtle, #f8fafc)',
          borderRadius: '8px',
          border: '1px solid var(--border-subtle, #e2e8f0)',
          padding: '8px',
          boxSizing: 'border-box',
        }}
      >
        <svg
          viewBox="0 0 540 180"
          style={{ width: '100%', minWidth: '460px', height: '170px', display: 'block' }}
          role="img"
          aria-label={diagram.title}
        >
          <defs>
            <marker
              id={`arrow-${diagramUid}`}
              viewBox="0 0 10 10"
              refX="8"
              refY="5"
              markerWidth="6"
              markerHeight="6"
              orient="auto-start-reverse"
            >
              <path d="M 0 1 L 9 5 L 0 9 z" fill="#64748b" />
            </marker>
            <marker
              id={`arrow-repair-${diagramUid}`}
              viewBox="0 0 10 10"
              refX="8"
              refY="5"
              markerWidth="6"
              markerHeight="6"
              orient="auto-start-reverse"
            >
              <path d="M 0 1 L 9 5 L 0 9 z" fill="#16a34a" />
            </marker>
          </defs>

          {/* Render directed edges */}
          {diagram.edges.map((edge) => {
            const fromNode = diagram.nodes.find((n) => n.id === edge.from)
            const toNode = diagram.nodes.find((n) => n.id === edge.to)
            if (!fromNode || !toNode) return null

            const chosenTarget = edge.status === 'needs_repair' && repairTarget
              ? diagram.nodes.find(node => node.id === repairTarget) : undefined
            const isRepaired = Boolean(chosenTarget)
            const visibleTarget = chosenTarget || toNode

            const strokeColor = isRepaired ? '#2563eb' : edge.status === 'needs_repair' ? '#dc2626' : '#64748b'
            const strokeDash = edge.status === 'needs_repair' && !isRepaired ? '4,3' : 'none'

            const targetY = visibleTarget.y + 15

            return (
              <g key={edge.id}>
                <line
                  x1={fromNode.x + 85}
                  y1={fromNode.y + 15}
                  x2={visibleTarget.x - 5}
                  y2={targetY}
                  stroke={strokeColor}
                  strokeWidth="2"
                  strokeDasharray={strokeDash}
                  markerEnd={`url(#arrow-${diagramUid})`}
                />
                <text
                  x={(fromNode.x + visibleTarget.x + 80) / 2}
                  y={(fromNode.y + targetY) / 2 - 6}
                  fontSize="10"
                  fill={strokeColor}
                  textAnchor="middle"
                  fontWeight="600"
                >
                  {isRepaired ? `selected: ${visibleTarget.label}` : edge.label}
                </text>
              </g>
            )
          })}

          {/* Render nodes */}
          {diagram.nodes.map((node) => {
            const colors = getNodeColor(node.type)
            const isSelectedTarget = repairTarget === node.id
            const matchingBlank = diagram.blanks?.find(blank => blank.id === node.id)
              || (diagram.blanks?.length === 1 ? diagram.blanks[0] : undefined)
            const selectedBlank = matchingBlank ? blankSelections[matchingBlank.id] || (value?.blank_id === matchingBlank.id || diagram.blanks?.length === 1 ? legacyBlank : '') : ''
            const isReplacedBlank = node.type === 'blank' && selectedBlank

            return (
              <g key={node.id} transform={`translate(${node.x}, ${node.y})`}>
                <rect
                  width="110"
                  height="34"
                  rx="6"
                  fill={isSelectedTarget ? '#eff6ff' : colors.bg}
                  stroke={isSelectedTarget ? '#2563eb' : colors.border}
                  strokeWidth={isSelectedTarget ? '2.5' : '1.5'}
                />
                <text
                  x="55"
                  y="21"
                  fontSize="11"
                  fontWeight="600"
                  fill={colors.text}
                  textAnchor="middle"
                >
                  {isReplacedBlank ? selectedBlank : node.label}
                </text>
              </g>
            )
          })}
        </svg>
      </div>

      {/* Interactive Controls (Repair / Completion) */}
      {diagram.repair_options && diagram.repair_options.length > 0 && (
        <div style={{ marginTop: '12px' }}>
          <div style={{ fontSize: '12px', fontWeight: 600, marginBottom: '6px', color: 'var(--text-secondary, #334155)' }}>
            Choose a diagram repair:
          </div>
          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
            {diagram.repair_options.map((opt) => {
              const active = selectedRepair === opt.id
              return (
                <button
                  key={opt.id}
                  type="button"
                  disabled={readOnly}
                  aria-pressed={active}
                  onClick={() => handleRepairChange(opt.id)}
                  style={{
                    padding: '6px 14px',
                    borderRadius: '6px',
                    fontSize: '12px',
                    fontWeight: 600,
                    cursor: readOnly ? 'default' : 'pointer',
                    border: active ? '2px solid #2563eb' : '1px solid var(--border-color, #cbd5e1)',
                    background: active ? '#eff6ff' : 'var(--surface-color, #ffffff)',
                    color: active ? '#1d4ed8' : 'var(--text-primary, #1e293b)',
                    transition: 'all 0.15s ease',
                  }}
                >
                  {opt.label} {active && '✓'}
                </button>
              )
            })}
          </div>
        </div>
      )}

      {diagram.blanks && diagram.blanks.length > 0 && (
        <div style={{ marginTop: '12px' }}>
          {diagram.blanks.map((b) => (
            <div key={b.id} style={{ marginBottom: '8px' }}>
              <div style={{ fontSize: '12px', fontWeight: 600, marginBottom: '6px', color: 'var(--text-secondary, #334155)' }}>
                {b.prompt}
              </div>
              <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                {b.options.map((opt) => {
                  const active = (blankSelections[b.id] || (value?.blank_id === b.id || diagram.blanks?.length === 1 ? legacyBlank : '')) === opt
                  return (
                    <button
                      key={opt}
                      type="button"
                      disabled={readOnly}
                      aria-pressed={active}
                      onClick={() => handleBlankChange(b.id, opt)}
                      style={{
                        padding: '6px 14px',
                        borderRadius: '6px',
                        fontSize: '12px',
                        fontWeight: 600,
                        cursor: readOnly ? 'default' : 'pointer',
                        border: active ? '2px solid #2563eb' : '1px solid var(--border-color, #cbd5e1)',
                        background: active ? '#eff6ff' : 'var(--surface-color, #ffffff)',
                        color: active ? '#1d4ed8' : 'var(--text-primary, #1e293b)',
                        transition: 'all 0.15s ease',
                      }}
                    >
                      {opt} {active && '✓'}
                    </button>
                  )
                })}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
