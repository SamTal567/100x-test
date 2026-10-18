import React, { useState, useEffect } from 'react'
import { api } from '../api/client'
import type { Concept, SessionListItem } from '../types'

interface CataloguePageProps {
  onSelectConcept: (conceptId: string) => void
  onResumeSession: (sessionId: string) => void
  onOpenReviewer?: () => void
}

export const CataloguePage: React.FC<CataloguePageProps> = ({
  onSelectConcept,
  onResumeSession,
}) => {
  const [concepts, setConcepts] = useState<Concept[]>([])
  const [sessions, setSessions] = useState<SessionListItem[]>([])
  const [loading, setLoading] = useState(true)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)
  const [reloadCount, setReloadCount] = useState(0)

  useEffect(() => {
    let active = true
    Promise.all([api.getConcepts(), api.listSessions()]).then(([conceptsData, sessionsData]) => {
      if (!active) return
      setConcepts(conceptsData)
      setSessions(sessionsData)
    }).catch((err: unknown) => {
      if (!active) return
      const msg = err instanceof Error ? err.message : String(err)
      setErrorMsg(`Failed to connect to backend: ${msg}. Verify the FastAPI server is running.`)
    }).finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [reloadCount])

  const handleStartSession = (concept: Concept) => {
    if (!concept.enabled) return
    onSelectConcept(concept.id)
  }

  // Active concept is Storage & Persistence
  const activeConcept = concepts.find(c => c.enabled && c.slug === 'storage-persistence') || concepts.find(c => c.enabled)
  const secondaryConcepts = concepts.filter(c => !c.enabled)
  const otherEnabledConcepts = concepts.filter(c => c.enabled && c.id !== activeConcept?.id)

  // Unfinished sessions
  const unfinishedSessions = sessions.filter(s => s.stage !== 'completed' && s.stage !== 'review')
  const completedSessions = sessions.filter(s => s.stage === 'completed' || s.stage === 'review')

  const getStageFriendlyLabel = (stage: string) => {
    switch (stage) {
      case 'diagnostic':
        return 'Stage 1: Baseline Reasoning'
      case 'investigate':
        return 'Stage 2: Targeted Follow-up'
      case 'apply':
        return 'Stage 3: Fresh Transfer Case'
      case 'review':
        return 'Stage 4: Evidence Report Ready'
      default:
        return stage.toUpperCase()
    }
  }

  return (
    <div className="catalogue-container">
      {/* Welcome Banner */}
      <section className="card welcome-card mb-4" aria-labelledby="catalogue-heading">
        <h1 id="catalogue-heading" className="welcome-title">
          Backend Fundamentals Check
        </h1>
        <p className="welcome-desc">
          Explain backend mechanisms from first principles, clarify specific points in your reasoning,
          and demonstrate understanding on unfamiliar transfer scenarios.
        </p>
      </section>

      {errorMsg && (
        <div className="error-banner mb-4" role="alert">
          <span className="error-icon" aria-hidden="true">⚠️</span>
          <span>{errorMsg}</span>
          <button type="button" className="btn btn-sm btn-secondary" onClick={() => { setLoading(true); setErrorMsg(null); setReloadCount(value => value + 1) }} style={{ marginLeft: 'auto' }}>
            Retry
          </button>
        </div>
      )}

      {/* Unfinished Session Resume Banner */}
      {unfinishedSessions.length > 0 && (
        <section className="card resume-card mb-4" aria-labelledby="resume-heading">
          <div className="resume-header">
            <span className="resume-icon" aria-hidden="true">📂</span>
            <div>
              <h2 id="resume-heading" className="resume-title">
                Resume In-Progress Session
              </h2>
              <p className="resume-desc">
                You have an unfinished session saved on this browser.
              </p>
            </div>
          </div>

          <div className="session-list">
            {unfinishedSessions.map((s) => (
              <div
                key={s.id}
                className="session-resume-item"
              >
                <div className="session-item-details">
                  <div className="session-item-title">
                    {s.concept_title || 'Storage & Persistence'}
                  </div>
                  <div className="session-item-meta">
                    <span className="stage-badge-pill">
                      {getStageFriendlyLabel(s.stage)}
                    </span>
                    <span className="session-date">
                      Last active: {new Date(s.updated_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}, {new Date(s.updated_at).toLocaleDateString()}
                    </span>
                  </div>
                </div>
                <button
                  type="button"
                  className="btn btn-primary btn-sm resume-action-btn"
                  onClick={() => onResumeSession(s.id)}
                  aria-label={`Resume session for ${s.concept_title || 'Storage & Persistence'}`}
                >
                  Resume Session →
                </button>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Completed Session History Banner */}
      {completedSessions.length > 0 && (
        <section className="card resume-card mb-4" aria-labelledby="completed-heading">
          <div className="resume-header">
            <span className="resume-icon" aria-hidden="true">📋</span>
            <div>
              <h2 id="completed-heading" className="resume-title">
                Completed Sessions & Evidence Reports
              </h2>
              <p className="resume-desc">
                Review your saved diagnostic and transfer reasoning results without regrading.
              </p>
            </div>
          </div>

          <div className="session-list">
            {completedSessions.map((s) => (
              <div
                key={s.id}
                className="session-resume-item"
              >
                <div className="session-item-details">
                  <div className="session-item-title">
                    {s.concept_title || 'Storage & Persistence'}
                  </div>
                  <div className="session-item-meta">
                    <span className="stage-badge-pill" style={{ background: 'var(--color-surface)', border: '1px solid var(--border-color)', color: 'var(--color-text)' }}>
                      {s.stage === 'review' ? 'Legacy session • Report ready' : 'Completed • Report ready'}
                    </span>
                    <span className="session-date">
                      Finished: {new Date(s.updated_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}, {new Date(s.updated_at).toLocaleDateString()}
                    </span>
                  </div>
                </div>
                <button
                  type="button"
                  className="btn btn-secondary btn-sm resume-action-btn"
                  onClick={() => onResumeSession(s.id)}
                  aria-label={`View evidence report for ${s.concept_title || 'Storage & Persistence'}`}
                >
                  View Evidence Report →
                </button>
              </div>
            ))}
          </div>
        </section>
      )}

      {loading && (
        <div className="loading-container" role="status" aria-live="polite">
          <div className="spinner" />
          <span>Loading concept catalogue...</span>
        </div>
      )}

      {!loading && activeConcept && (
        <div className="catalogue-sections">
          {/* Featured Primary Focus: Storage & Persistence */}
          <section className="card featured-concept-card mb-5" aria-labelledby="featured-concept-title">
            <div className="featured-card-topbar">
              <span className="module-tag-badge">MODULE B • HOW AN APP REMEMBERS</span>
              <span className="status-live-pill">
                <span className="live-dot" aria-hidden="true" />
                Active Focus Area
              </span>
            </div>

            <h2 id="featured-concept-title" className="featured-concept-title">
              {activeConcept.title}
            </h2>

            <p className="featured-concept-desc">
              {activeConcept.description}
            </p>

            <div className="pedagogy-walkthrough-grid">
              <div className="pedagogy-step-card">
                <div className="step-num">Step 1</div>
                <div className="step-label">Baseline Diagnostic</div>
                <p className="step-desc">
                  Explain what happens in 3 short scenarios involving process memory, server restarts, and disk persistence.
                </p>
              </div>

              <div className="pedagogy-step-card">
                <div className="step-num">Step 2</div>
                <div className="step-label">Targeted Follow-up</div>
                <p className="step-desc">
                  If an omission or ambiguity appears, receive a focused question to clarify your reasoning.
                </p>
              </div>

              <div className="pedagogy-step-card">
                <div className="step-num">Step 3</div>
                <div className="step-label">Fresh Transfer Case</div>
                <p className="step-desc">
                  Apply the same principle to an unfamiliar scenario to evaluate reasoning against prepared criteria.
                </p>
              </div>
            </div>

            <div className="what-this-reveals-box">
              <div className="reveals-title">What this session reveals:</div>
              <p className="reveals-text">
                Evaluates whether you distinguish process lifetime from durable storage, understand flush and commit boundaries,
                and can predict failure and recovery behavior from first principles.
              </p>
            </div>

            <div className="featured-action-row">
              <button
                type="button"
                className="btn btn-primary btn-lg start-session-btn"
                onClick={() => handleStartSession(activeConcept)}
              >
                <span>Start Storage & Persistence Session</span>
                <span aria-hidden="true">→</span>
              </button>
            </div>
          </section>

          {otherEnabledConcepts.length > 0 && <section className="secondary-modules-section" aria-labelledby="more-concepts-heading">
            <div className="section-header-row mb-3"><div><h3 id="more-concepts-heading" className="secondary-section-title">More backend concepts</h3><p className="secondary-section-desc">Authored development cases await human review. Each concept keeps its own saved evidence.</p></div></div>
            <div className="roadmap-grid">{otherEnabledConcepts.map(concept => <div key={concept.id} className="roadmap-card"><span className="roadmap-module-tag">Module {concept.module}</span><h4 className="roadmap-title">{concept.title}</h4><p className="roadmap-desc">{concept.description}</p><button type="button" className="btn btn-primary btn-sm" onClick={() => handleStartSession(concept)}>Start {concept.title}</button></div>)}</div>
          </section>}
          {/* Secondary / Upcoming Modules Roadmap (Honestly Labelled) */}
          {secondaryConcepts.length > 0 && <section className="secondary-modules-section" aria-labelledby="roadmap-heading">
            <div className="section-header-row mb-3">
              <div>
                <h3 id="roadmap-heading" className="secondary-section-title">
                  Upcoming Module 2 Concepts (Roadmap)
                </h3>
                <p className="secondary-section-desc">
                  The demo is intentionally focused on Storage & Persistence. The concepts below are planned for subsequent milestones.
                </p>
              </div>
            </div>

            <div className="roadmap-grid">
              {secondaryConcepts.map((concept) => (
                <div key={concept.id} className="roadmap-card">
                  <div className="roadmap-card-header">
                    <span className="roadmap-module-tag">Module {concept.module}</span>
                    <span className="roadmap-status-badge">Planned</span>
                  </div>
                  <div className="roadmap-title">{concept.title}</div>
                  <p className="roadmap-desc">{concept.description}</p>
                </div>
              ))}
            </div>
          </section>}
        </div>
      )}
    </div>
  )
}

