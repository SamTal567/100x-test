import React, { useState, useEffect, useRef } from 'react'
import type { User } from '../types'

interface AuthModalProps {
  isOpen: boolean
  onClose: () => void
  onAuthSuccess: (user: User) => void
}

export const AuthModal: React.FC<AuthModalProps> = ({ isOpen, onClose, onAuthSuccess }) => {
  const dialogRef = useRef<HTMLDialogElement>(null)
  const [mode, setMode] = useState<'signin' | 'signup'>('signin')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [fullName, setFullName] = useState('')
  const [errorMsg, setErrorMsg] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (isOpen) {
      if (!dialogRef.current?.open) {
        dialogRef.current?.showModal()
      }
    } else {
      if (dialogRef.current?.open) {
        dialogRef.current?.close()
      }
    }
  }, [isOpen])


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

        onClose()
      } else {
        const res = await api.login({
          email: email.trim(),
          password,
        })
        onAuthSuccess(res.user)
        onClose()
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err)
      setErrorMsg(msg)
    } finally {
      setLoading(false)
    }
  }

  const handleBackdropClick = (e: React.MouseEvent<HTMLDialogElement>) => {
    if (e.target === dialogRef.current) {
      onClose()
    }
  }

  if (!isOpen) return null

  return (
    <dialog
      ref={dialogRef}
      className="auth-modal-dialog card"
      onClick={handleBackdropClick}
      onCancel={(e) => {
        e.preventDefault()
        onClose()
      }}
      aria-labelledby="auth-modal-title"
    >
      <div className="auth-modal-content">
        <div className="auth-modal-header">
          <h2 id="auth-modal-title" className="auth-modal-title">
            {mode === 'signin' ? 'Sign In to Concept Check' : 'Create an Account'}
          </h2>
          <button
            type="button"
            className="auth-modal-close-btn"
            onClick={onClose}
            aria-label="Close dialog"
          >
            ✕
          </button>
        </div>

        <p className="auth-modal-desc">
          {mode === 'signin'
            ? 'Sign in to access your saved session history, progress reports, and personalized feedback.'
            : 'Register to link all your baseline diagnostic answers, practice exercises, and unfamiliar-case evidence to your account.'}
        </p>

        <div className="auth-mode-switch" role="tablist">
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
            <span>⚠️</span>
            <span>{errorMsg}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="auth-form">
          {mode === 'signup' && (
            <div className="auth-field">
              <label htmlFor="auth-fullname">Full Name (optional)</label>
              <input
                id="auth-fullname"
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
            <label htmlFor="auth-email">Email Address</label>
            <input
              id="auth-email"
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
            <label htmlFor="auth-password">Password</label>
            <input
              id="auth-password"
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
                <span>Processing...</span>
              ) : mode === 'signin' ? (
                <span>Sign In →</span>
              ) : (
                <span>Create Account →</span>
              )}
            </button>
            <button
              type="button"
              className="btn btn-secondary auth-cancel-btn"
              onClick={onClose}
              disabled={loading}
            >
              Cancel
            </button>
          </div>
        </form>
      </div>
    </dialog>
  )
}
