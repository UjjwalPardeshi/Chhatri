/** The mini-app root: the `.miniapp` scope and the portal container for dialogs, sheets and tooltips. */
import { createContext, useContext, useState, type ReactNode } from 'react'

import './miniapp.css'

const PortalContainerContext = createContext<HTMLElement | null>(null)

/** Radix portals render into this element so they stay inside `.miniapp` (CSS variables live there). */
export function useMiniappPortalContainer(): HTMLElement | null {
  return useContext(PortalContainerContext)
}

export function MiniappRoot({ children }: { children: ReactNode }) {
  const [root, setRoot] = useState<HTMLDivElement | null>(null)
  return (
    <div ref={setRoot} className="miniapp relative h-full w-full overflow-hidden [contain:layout_paint]">
      <PortalContainerContext.Provider value={root}>{children}</PortalContainerContext.Provider>
    </div>
  )
}
