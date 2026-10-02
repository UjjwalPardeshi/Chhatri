/** The mini-app root: the `.miniapp` scope, the language of the app (`lang`, so Hindi text gets Hindi line height) and the portal container for dialogs, sheets and popovers. */
import { createContext, useContext, useState, type ReactNode } from 'react'

import type { Lang } from './lib/lang'
import './miniapp.css'

const PortalContainerContext = createContext<HTMLElement | null>(null)

/** Radix portals render into this element so they stay inside `.miniapp`, where the scoped base and `contain: layout` apply. */
export function useMiniappPortalContainer(): HTMLElement | null {
  return useContext(PortalContainerContext)
}

export function MiniappRoot({ children, lang }: { children: ReactNode; lang?: Lang }) {
  const [root, setRoot] = useState<HTMLDivElement | null>(null)
  return (
    <div ref={setRoot} lang={lang} data-testid="app-root" className="miniapp h-full w-full">
      <PortalContainerContext.Provider value={root}>{children}</PortalContainerContext.Provider>
    </div>
  )
}
