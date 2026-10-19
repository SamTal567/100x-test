import React, { useState } from 'react'
import type { User } from '../types'

interface AuthPageProps {
  onAuthSuccess: (user: User) => void
}

export const AuthPage: React.FC<AuthPageProps> = ({ onAuthSuccess }) => {
  const [mode, setMode] = useState<'signin' | 'signup'>('signin')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [fullName, setFullName] = useState('')
  const [errorMsg, setErrorMsg] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setErrorMsg(null)
    setLoading(true)

    try {
      const { api } = await import('../api/client')
      if (mode === 'signup') {
        const res = await api.signup({
          email: email.trim(),
          password,
          full_name: fullName.trim() || undefined,
        })
        onAuthSuccess(res.user)
      } else {
        const res = await api.login({
          email: email.trim(),
          password,
        })
        onAuthSuccess(res.user)
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err)
      setErrorMsg(msg)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="auth-page-container">
      <div className="auth-page-card card">
        <div className="auth-page-hero">
          <div className="auth-brand-badge">
            <span className="auth-brand-icon" aria-hidden="true">💾</span>
            <span className="auth-brand-tag">Concept Check • Module 2</span>
          </div>
          <h1 className="auth-page-title">
            {mode === 'signin' ? 'Sign In to Continue' : 'Create Your Account'}
          </h1>
          <p className="auth-page-desc">
            {mode === 'signin'
              ? 'Sign in to access your concept diagnostic sessions, personalized tutoring feedback, and progress reports.'
              : 'Create an account to start your backend reasoning assessments and save your evidence across devices.'}
          </p>
        </div>

        <div className="auth-mode-switch" role="tablist" aria-label="Authentication mode">
          <button
            type="button"
            role="tab"
            aria-selected={mode === 'signin'}
            className={`auth-tab-btn ${mode === 'signin' ? 'active' : ''}`}
            onClick={() => {
              setMode('signin')
              setErrorMsg(null)
            }}
          >
            Sign In
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={mode === 'signup'}
            className={`auth-tab-btn ${mode === 'signup' ? 'active' : ''}`}
            onClick={() => {
              setMode('signup')
              setErrorMsg(null)
            }}
          >
            Create Account
          </button>
        </div>

        {errorMsg && (
          <div className="auth-error-banner" role="alert">
            <span aria-hidden="true">⚠️</span>
            <span>{errorMsg}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="auth-form">
          {mode === 'signup' && (
            <div className="auth-field">
              <label htmlFor="auth-page-fullname">Full Name (optional)</label>
              <input
                id="auth-page-fullname"
                type="text"
                className="input"
                placeholder="e.g. Alex Chen"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                autoComplete="name"
              />
            </div>
          )}

          <div className="auth-field">
            <label htmlFor="auth-page-email">Email Address</label>
            <input
              id="auth-page-email"
              type="email"
              className="input"
              placeholder="learner@example.com"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="email"
              autoFocus
            />
          </div>

          <div className="auth-field">
            <label htmlFor="auth-page-password">Password</label>
            <input
              id="auth-page-password"
              type="password"
              className="input"
              placeholder={mode === 'signup' ? 'At least 6 characters' : 'Enter your password'}
              required
              minLength={mode === 'signup' ? 6 : 1}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete={mode === 'signup' ? 'new-password' : 'current-password'}
            />
          </div>

          <div className="auth-actions">
            <button
              type="submit"
              className="btn btn-primary auth-submit-btn"
              disabled={loading}
            >
              {loading ? (
                <span>Authenticating...</span>
              ) : mode === 'signin' ? (
                <span>Sign In →</span>
              ) : (
                <span>Create Account & Start Learning →</span>
              )}
            </button>
          </div>
        </form>

        <div className="auth-page-footer">
          {mode === 'signin' ? (
            <p className="auth-toggle-hint">
              Don't have an account yet?{' '}
              <button
                type="button"
                className="btn-text-link"
                onClick={() => {
                  setMode('signup')
                  setErrorMsg(null)
                }}
              >
                Create one now
              </button>
            </p>
          ) : (
            <p className="auth-toggle-hint">
              Already have an account?{' '}
              <button
                type="button"
                className="btn-text-link"
                onClick={() => {
                  setMode('signin')
                  setErrorMsg(null)
                }}
              >
                Sign in here
              </button>
            </p>
          )}
        </div>
      </div>
    </div>
  )
}
