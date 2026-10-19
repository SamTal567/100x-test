import { useState, useEffect, useCallback, useRef } from 'react'
import { CataloguePage } from './pages/CataloguePage'
import { SessionPage } from './pages/SessionPage'
import { AuthPage } from './pages/AuthPage'
import { ThemeToggle } from './components/ThemeToggle'
import { ReviewerDrawer } from './components/ReviewerDrawer'
import { api, AUTH_REQUIRED_EVENT } from './api/client'
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
  const [authError, setAuthError] = useState<string | null>(null)
  const identity = useRef<User | null>(null)
  const authVersion = useRef(0)

  const clearIdentity = useCallback((message: string | null = null) => {
    authVersion.current += 1
    identity.current = null
    setCurrentUser(null)
    setCurrentSessionId(null)
    setActiveView('catalogue')
    setReviewerOpen(false)
    setAuthLoading(false)
    setAuthError(message)
    localStorage.removeItem('cc_active_session_id')
    localStorage.removeItem('cc_active_session_owner')
    localStorage.removeItem('cc_active_view')
  }, [])

  const checkAuthentication = useCallback(async (restoreSelection = false) => {
    const version = ++authVersion.current
    try {
      const result = await api.getMe()
      if (version !== authVersion.current) return
      if (result.authenticated && result.user) {
        const previousId = identity.current?.id
        identity.current = result.user
        setCurrentUser(result.user)
        if (previousId !== result.user.id) {
          setCurrentSessionId(null)
          setActiveView('catalogue')
          setReviewerOpen(false)
        }
        // Read the saved selection only after its account has been verified.
        if (restoreSelection && localStorage.getItem('cc_active_session_owner') === result.user.id) {
          const savedSession = localStorage.getItem('cc_active_session_id')
          if (savedSession && localStorage.getItem('cc_active_view') === 'session') {
            setCurrentSessionId(savedSession)
            setActiveView('session')
          }
        }
        setAuthLoading(false)
      } else {
        clearIdentity(identity.current ? 'Your sign-in expired. Sign in again to access your saved sessions.' : null)
      }
    } catch {
      if (version !== authVersion.current) return
      setAuthError('Authentication could not be checked. Check your connection and retry.')
      setAuthLoading(false)
    }
  }, [clearIdentity])

  useEffect(() => {
    if (!authLoading && currentUser) {
      localStorage.setItem('cc_active_view', activeView)
    }
  }, [activeView, currentUser, authLoading])

  useEffect(() => {
    if (!authLoading && currentUser) {
      localStorage.setItem('cc_active_session_owner', currentUser.id)
      if (currentSessionId) localStorage.setItem('cc_active_session_id', currentSessionId)
      else localStorage.removeItem('cc_active_session_id')
    }
  }, [currentSessionId, currentUser, authLoading])

  useEffect(() => {
    api.getHealth().then(setHealth).catch(() => null)
    void Promise.resolve().then(() => checkAuthentication(true))
    return () => { authVersion.current += 1 }
  }, [checkAuthentication])

  useEffect(() => {
    const expired = () => clearIdentity('Your sign-in expired. Sign in again to access your saved sessions. Your submitted answers are saved.')
    const changed = (event: StorageEvent) => {
      if (event.key !== 'cc_auth_token') return
      // Hide the previous account while verifying the new shared browser identity.
      identity.current = null
      setCurrentUser(null)
      setCurrentSessionId(null)
      setReviewerOpen(false)
      setAuthLoading(true)
      setAuthError(null)
      void checkAuthentication()
    }
    window.addEventListener(AUTH_REQUIRED_EVENT, expired)
    window.addEventListener('storage', changed)
    return () => {
      window.removeEventListener(AUTH_REQUIRED_EVENT, expired)
      window.removeEventListener('storage', changed)
    }
  }, [checkAuthentication, clearIdentity])

  const handleLogout = async () => {
    const version = authVersion.current
    try {
      await api.logout()
      if (version === authVersion.current) clearIdentity()
    } catch {
      if (version === authVersion.current) setAuthError('Sign-out could not be confirmed. You are still signed in. Check your connection and try Sign Out again.')
    }
  }

  const handleAuthSuccess = (user: User) => {
    authVersion.current += 1
    identity.current = user
    setCurrentUser(user)
    setCurrentSessionId(null)
    setActiveView('catalogue')
    setAuthError(null)
    setAuthLoading(false)
  }

  const handleSelectConcept = async (conceptId: string) => {
    const version = authVersion.current
    try {
      const newSession = await api.createSession(conceptId)
      if (version !== authVersion.current) return
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
        {authError && <div className="error-banner mb-4" role="alert">
          <span>{authError}</span>
          <button type="button" className="btn btn-secondary btn-sm" onClick={() => { setAuthLoading(true); setAuthError(null); void checkAuthentication(true) }} disabled={authLoading}>Retry authentication</button>
        </div>}
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
