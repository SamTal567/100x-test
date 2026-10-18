import React, { useState } from 'react'
import { openTrackedResource } from '../lib/trackedResources'

export type ResourceOpening = (url: string) => Promise<boolean>

export const TrackedResourceLink: React.FC<{
  url: string; onOpenResource?: ResourceOpening; disabled?: boolean; className?: string; children: React.ReactNode
}> = ({ url, onOpenResource, disabled, className, children }) => {
  const [busy, setBusy] = useState(false)
  const [failed, setFailed] = useState(false)
  const open = async () => {
    if (!onOpenResource || disabled || busy) return
    setBusy(true)
    setFailed(false)
    const saved = await openTrackedResource(url, () => onOpenResource(url))
    setFailed(!saved)
    setBusy(false)
  }
  return <span className="tracked-resource-control">
    <button type="button" className={className || 'btn btn-secondary btn-sm'} disabled={disabled || busy || !onOpenResource} onClick={open}>{busy ? 'Recording guide opening…' : children}</button>
    {failed && <span className="provider-failure" role="status">The guide could not be opened with its help event confirmed. Please retry.</span>}
  </span>
}
