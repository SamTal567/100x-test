import React, { useEffect, useState } from 'react'

export type Theme = 'light' | 'dark'

interface ThemeToggleProps {
  className?: string
}

export const ThemeToggle: React.FC<ThemeToggleProps> = ({ className = '' }) => {
  const [theme, setTheme] = useState<Theme>(() => {
    const saved = localStorage.getItem('cc_theme') as Theme
    if (saved === 'dark' || saved === 'light') return saved
    return 'light' // Theme A (Pastel Desktop) is default
  })

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
    localStorage.setItem('cc_theme', theme)
  }, [theme])

  const toggleTheme = () => {
    setTheme(prev => (prev === 'light' ? 'dark' : 'light'))
  }

  const isDark = theme === 'dark'

  return (
    <button
      type="button"
      className={`theme-toggle-btn ${className}`}
      onClick={toggleTheme}
      aria-label={`Current theme: ${isDark ? 'Midnight Terminal (dark)' : 'Pastel Desktop (light)'}. Click to switch.`}
      aria-pressed={isDark}
      title={isDark ? 'Switch to Pastel Desktop (Theme A)' : 'Switch to Midnight Terminal (Theme C)'}
    >
      <span className="theme-toggle-icon" aria-hidden="true">
        {isDark ? '💻' : '🎨'}
      </span>
      <span className="theme-toggle-text">
        {isDark ? 'Midnight Terminal' : 'Pastel Desktop'}
      </span>
    </button>
  )
}

