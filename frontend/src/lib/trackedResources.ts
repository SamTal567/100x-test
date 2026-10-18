import { safeResourceUrl } from './sessionDrafts'

interface ResourceTab {
  opener: unknown
  location: Pick<Location, 'replace'>
  close: () => void
}
interface ResourceHost {
  open: (url: string, target: string) => ResourceTab | null
  location: Pick<Location, 'assign'>
}

export async function openTrackedResource(raw: string, saveOpening: () => Promise<boolean>, host: ResourceHost = window): Promise<boolean> {
  const url = safeResourceUrl(raw)
  if (!url) return false
  // Reserve an empty tab during the click gesture. It receives no lesson until
  // the server confirms persistence; sever its opener before any navigation.
  let tab: ResourceTab | null = null
  try {
    tab = host.open('about:blank', '_blank')
    if (tab) tab.opener = null
    if (!await saveOpening()) { tab?.close(); return false }
    if (tab) tab.location.replace(url)
    else host.location.assign(url)
    return true
  } catch {
    tab?.close()
    return false
  }
}
