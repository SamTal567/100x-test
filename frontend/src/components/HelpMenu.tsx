import React, { useEffect, useRef, useState } from 'react'

export interface HelpMenuProps {
  canTeaching: boolean
  canPractice: boolean
  canResource: boolean
  canClarify: boolean
  canCorrectAi: boolean
  disabled: boolean
  onSelect: (action: 'teaching' | 'practice' | 'resource' | 'clarify' | 'correct_ai') => void
}

interface MenuItemDef {
  key: 'teaching' | 'practice' | 'resource' | 'clarify' | 'correct_ai'
  title: string
  sub: string
  icon: string
  available: boolean
}

export const HelpMenu: React.FC<HelpMenuProps> = ({
  canTeaching,
  canPractice,
  canResource,
  canClarify,
  canCorrectAi,
  disabled,
  onSelect,
}) => {
  const [open, setOpen] = useState(false)
  const [focusedIndex, setFocusedIndex] = useState<number>(-1)
  const menuRef = useRef<HTMLDivElement>(null)
  const triggerRef = useRef<HTMLButtonElement>(null)
  const itemRefs = useRef<(HTMLButtonElement | null)[]>([])

  const items: MenuItemDef[] = [
    {
      key: 'teaching',
      title: 'Explain this concept',
      sub: 'Request a fuller explanation from the tutor',
      icon: '📖',
      available: canTeaching,
    },
    {
      key: 'practice',
      title: 'Try guided practice',
      sub: 'Step through a focused practice exercise',
      icon: '✏️',
      available: canPractice,
    },
    {
      key: 'resource',
      title: 'Open concept guide',
      sub: 'Read the prepared reference guide',
      icon: '📚',
      available: canResource,
    },
    {
      key: 'clarify',
      title: 'Ask about the scenario',
      sub: 'Ask AI to explain the wording or stated facts',
      icon: '❓',
      available: canClarify,
    },
    {
      key: 'correct_ai',
      title: 'The tutor misunderstood me',
      sub: 'Clarify what your original answer intended',
      icon: '💬',
      available: canCorrectAi,
    },
  ]

  const activeItems = items.filter(item => item.available)

  useEffect(() => {
    if (!open) return
    const handleClickOutside = (e: MouseEvent | TouchEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setOpen(false)
        setFocusedIndex(-1)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    document.addEventListener('touchstart', handleClickOutside)
    return () => {
      document.removeEventListener('mousedown', handleClickOutside)
      document.removeEventListener('touchstart', handleClickOutside)
    }
  }, [open])

  useEffect(() => {
    if (open && focusedIndex >= 0 && itemRefs.current[focusedIndex]) {
      itemRefs.current[focusedIndex]?.focus()
    }
  }, [open, focusedIndex])

  if (!activeItems.length) return null

  const handleTriggerKeyDown = (e: React.KeyboardEvent<HTMLButtonElement>) => {
    if (disabled) return
    if (e.key === 'ArrowDown' || e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      setOpen(true)
      setFocusedIndex(0)
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setOpen(true)
      setFocusedIndex(activeItems.length - 1)
    }
  }

  const handleMenuKeyDown = (e: React.KeyboardEvent<HTMLDivElement>) => {
    if (e.key === 'Escape') {
      e.preventDefault()
      setOpen(false)
      triggerRef.current?.focus()
    } else if (e.key === 'ArrowDown') {
      e.preventDefault()
      setFocusedIndex(prev => (prev + 1) % activeItems.length)
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setFocusedIndex(prev => (prev - 1 + activeItems.length) % activeItems.length)
    } else if (e.key === 'Home') {
      e.preventDefault()
      setFocusedIndex(0)
    } else if (e.key === 'End') {
      e.preventDefault()
      setFocusedIndex(activeItems.length - 1)
    } else if (e.key === 'Tab') {
      setOpen(false)
    }
  }

  const handleSelect = (key: MenuItemDef['key']) => {
    setOpen(false)
    setFocusedIndex(-1)
    onSelect(key)
    triggerRef.current?.focus()
  }

  return (
    <div className="help-menu-container" ref={menuRef} onKeyDown={open ? handleMenuKeyDown : undefined}>
      <button
        ref={triggerRef}
        type="button"
        id="help-menu-toggle"
        className="btn btn-secondary help-menu-toggle"
        aria-haspopup="true"
        aria-expanded={open}
        aria-controls={open ? 'help-menu-dropdown' : undefined}
        disabled={disabled}
        onClick={() => {
          if (!open) {
            setOpen(true)
            setFocusedIndex(0)
          } else {
            setOpen(false)
          }
        }}
        onKeyDown={handleTriggerKeyDown}
      >
        More help ▾
      </button>
      {open && (
        <div
          id="help-menu-dropdown"
          className="help-menu-dropdown"
          role="menu"
          aria-labelledby="help-menu-toggle"
        >
          {activeItems.map((item, index) => (
            <button
              key={item.key}
              ref={el => { itemRefs.current[index] = el }}
              type="button"
              role="menuitem"
              tabIndex={focusedIndex === index ? 0 : -1}
              className={`help-menu-item ${focusedIndex === index ? 'focused' : ''}`}
              onClick={() => handleSelect(item.key)}
            >
              <span className="help-menu-icon" aria-hidden="true">{item.icon}</span>
              <div className="help-menu-text">
                <strong className="help-menu-title">{item.title}</strong>
                <span className="help-menu-sub">{item.sub}</span>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
