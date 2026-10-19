import React from 'react'

interface StageProgressBarProps {
  currentStage: 'diagnostic' | 'investigate' | 'apply' | 'review' | 'completed'
  completedStages?: string[]
  attemptedStages?: string[]
  recordedStages?: string[]
}

interface StageItem {
  key: string
  label: string
  shortDesc: string
}

const STAGES: StageItem[] = [
  { key: 'diagnostic', label: '1. Baseline Reasoning', shortDesc: 'Explain what happens and why' },
  { key: 'investigate', label: '2. Targeted Follow-up', shortDesc: 'Clarify specific reasoning' },
  { key: 'apply', label: '3. Fresh Scenario', shortDesc: 'Apply principles to a new case' },
  { key: 'review', label: '4. Evidence Report', shortDesc: 'Review findings & assistance history' },
]

export const StageProgressBar: React.FC<StageProgressBarProps> = ({
  currentStage,
  completedStages,
  attemptedStages,
  recordedStages = [],
}) => {
  const stageOrder = ['diagnostic', 'investigate', 'apply', 'review', 'completed']
  const currentIndex = stageOrder.indexOf(currentStage)

  return (
    <nav className="stage-progress-container" aria-label="Learning session progress">
      <ol className="stage-progress" role="list">
        {STAGES.map((s, idx) => {
          const isCurrent = currentStage === s.key || (currentStage === 'review' && s.key === 'review')
          const isPast = currentIndex > idx

          let status: 'completed' | 'attempted' | 'skipped' | 'current' | 'pending' = 'pending'
          if (isPast) {
            const completed = completedStages
              ? (s.key === 'review' ? currentStage === 'completed' : completedStages.includes(s.key))
              : (s.key === 'review' || recordedStages.includes(s.key))
            const attempted = attemptedStages ? attemptedStages.includes(s.key) : false
            if (completed) {
              status = 'completed'
            } else if (attempted) {
              status = 'attempted'
            } else {
              status = 'skipped'
            }
          } else if (isCurrent) {
            status = 'current'
          }

          const isDone = status === 'completed'
          const isAttempted = status === 'attempted'
          const isSkipped = status === 'skipped'
          const isActive = status === 'current'

          let dotContent = `${idx + 1}`
          if (isDone) dotContent = '✓'
          else if (isAttempted) dotContent = '◐'
          else if (isSkipped) dotContent = '—'

          let subtext = s.shortDesc
          if (isSkipped) subtext = 'Not attempted / Skipped'
          else if (isAttempted) subtext = s.key === 'investigate' ? 'Tutoring only (no revision)' : 'Partially attempted'
          else if (isDone && s.key === 'investigate') subtext = 'Revision submitted'
          else if (isDone && s.key === 'apply') subtext = 'Fresh case submitted'

          return (
            <React.Fragment key={s.key}>
              <li
                className={`stage-step ${isActive ? 'current' : ''}`}
                aria-current={isActive ? 'step' : undefined}
                aria-label={`${s.label}: ${status}`}
              >
                <div
                  className={`stage-dot ${isDone ? 'done' : isActive ? 'active' : isAttempted ? 'attempted' : isSkipped ? 'skipped' : 'pending'}`}
                  aria-hidden="true"
                >
                  {dotContent}
                </div>
                <div className="stage-info">
                  <span className={`stage-label ${isActive ? 'active' : ''}`}>{s.label}</span>
                  <span className="stage-subtext">{subtext}</span>
                </div>
              </li>
              {idx < STAGES.length - 1 && (
                <div
                  className={`stage-connector ${isDone ? 'done' : isAttempted ? 'attempted' : ''}`}
                  aria-hidden="true"
                />
              )}
            </React.Fragment>
          )
        })}
      </ol>
    </nav>
  )
}

