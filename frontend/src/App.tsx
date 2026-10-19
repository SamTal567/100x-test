import { useState, useEffect } from 'react'
import { CataloguePage } from './pages/CataloguePage'
import { SessionPage } from './pages/SessionPage'
import { AuthPage } from './pages/AuthPage'
import { ThemeToggle } from './components/ThemeToggle'
import { ReviewerDrawer } from './components/ReviewerDrawer'
import { api } from './api/client'
import type { HealthResponse, User } from './types'
import './index.css'


export function App() {
  const [currentUser, setCurrentUser] = useState<User | null>(null)
  const [authLoading, setAuthLoading] = useState(true)
  const [activeView, setActiveView] = useState<'catalogue' | 'session'>('catalogue')
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null)
  const [reviewerOpen, setReviewerOpen] = useState(false)
  const [reviewRevision, setReviewRevision] = useState(0)
  const [health, setHealth] = useState<HealthResponse | null>(null)

  useEffect(() => {
    if (currentUser) {
      localStorage.setItem('cc_active_view', activeView)
    }
  }, [activeView, currentUser])

  useEffect(() => {
    if (currentUser && currentSessionId) {
      localStorage.setItem('cc_active_session_id', currentSessionId)
    } else if (!currentUser) {
      localStorage.removeItem('cc_active_session_id')
    }
  }, [currentSessionId, currentUser])

  useEffect(() => {
    api.getHealth().then(setHealth).catch(() => null)
    api.getMe().then(res => {
      if (res.authenticated && res.user) {
        setCurrentUser(res.user)
        const savedSession = localStorage.getItem('cc_active_session_id')
        const savedView = localStorage.getItem('cc_active_view')
        if (savedSession && savedView === 'session') {
          setCurrentSessionId(savedSession)
          setActiveView('session')
        }
      } else {
        setCurrentUser(null)
      }
    }).catch(() => {
      setCurrentUser(null)
    }).finally(() => {
      setAuthLoading(false)
    })
  }, [])

  const handleLogout = async () => {
    try {
      await api.logout()
    } finally {
      setCurrentUser(null)
      setCurrentSessionId(null)
      setActiveView('catalogue')
      localStorage.removeItem('cc_active_session_id')
      localStorage.removeItem('cc_jwt_token')
    }
  }

  const handleAuthSuccess = (user: User) => {
    setCurrentUser(user)
    setActiveView('catalogue')
  }

  const handleSelectConcept = async (conceptId: string) => {
    try {
      const newSession = await api.createSession(conceptId)
      setCurrentSessionId(newSession.id)
      setActiveView('session')
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err)
      alert(`Could not start session: ${msg}`)
    }
  }

  const handleResumeSession = (sessionId: string) => {
    setCurrentSessionId(sessionId)
    setActiveView('session')
  }

  const handleBackToCatalogue = () => {
    setActiveView('catalogue')
  }

  return (
    <div className="app-layout">
      {/* Top Application Shell */}
      <header className="app-header">
        <div className="header-inner">
          <div className="header-brand-group">
            <button
              type="button"
              className="brand-btn"
              onClick={() => currentUser && setActiveView('catalogue')}
              title={currentUser ? 'Return to Concept Check Catalogue' : 'Concept Check'}
            >
              <span className="brand-icon" aria-hidden="true">💾</span>
              <span className="brand-title">Concept Check</span>
            </button>
            <span className="brand-badge">Module 2</span>
          </div>

          {currentUser && (
            <nav className="header-nav" aria-label="Main navigation">
              <button
                type="button"
                className={`nav-tab ${activeView === 'catalogue' ? 'active' : ''}`}
                onClick={() => setActiveView('catalogue')}
                aria-current={activeView === 'catalogue' ? 'page' : undefined}
              >
                <span className="tab-icon" aria-hidden="true">📚</span>
                <span>Catalogue</span>
              </button>

              {currentSessionId && (
                <button
                  type="button"
                  className={`nav-tab ${activeView === 'session' ? 'active' : ''}`}
                  onClick={() => setActiveView('session')}
                  aria-current={activeView === 'session' ? 'page' : undefined}
                >
                  <span className="tab-icon active-dot" aria-hidden="true">✏️</span>
                  <span>Current Session</span>
                </button>
              )}
            </nav>
          )}

          <div className="header-utilities">
            {/* Plain language provider status */}
            <div
              className="provider-status-badge"
              title={
                health?.openai_available
                  ? 'AI assistance is configured on the backend. Responses are evaluated per turn.'
                  : 'AI provider unavailable. Any local development guidance is labelled in each response.'
              }
            >
              <span className={`status-indicator-dot ${health?.openai_available ? 'active' : 'stub'}`} />
              <span className="status-indicator-text">
                {health?.openai_available ? 'AI Configured' : 'AI Unavailable'}
              </span>
            </div>

            {/* User Authentication state */}
            {currentUser && (
              <div className="user-profile-badge" title={`Signed in as ${currentUser.email}`}>
                <span className="user-avatar-initial" aria-hidden="true">
                  {(currentUser.full_name || currentUser.email)[0].toUpperCase()}
                </span>
                <span className="user-name-label">{currentUser.full_name || currentUser.email}</span>
                <button
                  type="button"
                  className="btn-auth-logout"
                  onClick={handleLogout}
                  title="Sign out of your account"
                >
                  Sign Out
                </button>
              </div>
            )}

            <ThemeToggle />
          </div>
        </div>
      </header>


      {/* Main Content Area — generous, unconstrained width */}
      <main className="app-main" id="main-content">
        {authLoading ? (
          <div className="auth-loading-state" role="status">
            <div className="loading-spinner" aria-hidden="true" />
            <p>Checking authentication status...</p>
          </div>
        ) : !currentUser ? (
          <AuthPage onAuthSuccess={handleAuthSuccess} />
        ) : (
          <>
            {activeView === 'catalogue' && (
              <CataloguePage
                onSelectConcept={handleSelectConcept}
                onResumeSession={handleResumeSession}
                onOpenReviewer={() => setReviewerOpen(true)}
              />
            )}

            {activeView === 'session' && currentSessionId && (
              <SessionPage
                key={currentSessionId}
                sessionId={currentSessionId}
                onBackToCatalogue={handleBackToCatalogue}
                onOpenReviewer={() => setReviewerOpen(true)}
                reviewRevision={reviewRevision}
                onOpenSession={handleResumeSession}
              />
            )}
          </>
        )}
      </main>

      {/* Quiet, unobtrusive footer */}
      <footer className="app-footer">
        <div className="footer-inner">
          <div className="footer-left">
            <span>100x Module 2 Backend Reasoning</span>
            {currentUser && currentSessionId && activeView === 'session' && (
              <span className="footer-session-ref">
                • Reference: <code className="code-ref">{currentSessionId.slice(0, 8)}</code>
              </span>
            )}
            {!currentUser && (
              <span className="footer-session-ref">
                • Authentication required
              </span>
            )}
          </div>
          <div className="footer-right">
            {/* Reviewer Desk kept as a secondary staff utility, not a prominent learner distraction */}
            <button
              type="button"
              className="footer-link-btn"
              onClick={() => setReviewerOpen(true)}
              title="Open Reviewer Desk for staff evaluation"
            >
              <span aria-hidden="true">🛡️</span> Staff Reviewer Desk
            </button>
          </div>
        </div>
      </footer>

      {/* Reviewer Modal / Drawer */}
      {reviewerOpen && <ReviewerDrawer
        isOpen={reviewerOpen}
        onClose={() => setReviewerOpen(false)}
        onReviewSubmitted={() => setReviewRevision(value => value + 1)}
      />}
    </div>
  )
}


export default App
