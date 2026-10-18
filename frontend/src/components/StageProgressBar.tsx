import React from 'react'

interface StageProgressBarProps {
  currentStage: 'diagnostic' | 'investigate' | 'apply' | 'review' | 'completed'
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

export const StageProgressBar: React.FC<StageProgressBarProps> = ({ currentStage, recordedStages = [] }) => {
  const stageOrder = ['diagnostic', 'investigate', 'apply', 'review', 'completed']
  const currentIndex = stageOrder.indexOf(currentStage)

  return (
    <nav className="stage-progress-container" aria-label="Learning session progress">
      <ol className="stage-progress" role="list">
        {STAGES.map((s, idx) => {
          const isDone = currentIndex > idx && (s.key === 'review' || recordedStages.includes(s.key))
          const isSkipped = currentIndex > idx && !isDone
          const isActive = currentStage === s.key || (currentStage === 'completed' && s.key === 'review')

          return (
            <React.Fragment key={s.key}>
              <li
                className={`stage-step ${isActive ? 'current' : ''}`}
                aria-current={isActive ? 'step' : undefined}
              >
                <div
                  className={`stage-dot ${isDone ? 'done' : isActive ? 'active' : 'pending'}`}
                  aria-hidden="true"
                >
                  {isDone ? '✓' : idx + 1}
                </div>
                <div className="stage-info">
                  <span className={`stage-label ${isActive ? 'active' : ''}`}>{s.label}</span>
                  <span className="stage-subtext">{isSkipped ? 'Not attempted' : s.shortDesc}</span>
                </div>
              </li>
              {idx < STAGES.length - 1 && (
                <div
                  className={`stage-connector ${isDone ? 'done' : ''}`}
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

