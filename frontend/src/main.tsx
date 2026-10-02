/** Console bootstrap: picks the real API or the in-browser mock (binding decision B7). */
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import App from './App'
import { ApiClient, type FetchLike } from './api/client'
import { createApi } from './api/endpoints'
import { isMockMode } from './config'
import { unknownFeatures } from './features'
import './styles/tokens.css'
import './styles/base.css'
import './styles/shell.css'
import './styles/provider-panel.css'
import './styles/replay-controls.css'
import './styles/live-map.css'
import './styles/live-panel.css'
import './styles/phone.css'
import './styles/merchant-panel.css'
import './styles/claims.css'
import './styles/claims-case.css'
import './styles/claims-evidence.css'
import './styles/pages.css'
import './styles/overview.css'
import './styles/overview-story.css'
import './styles/overview-demo.css'
import './styles/overview-tech.css'
import './styles/overview-value.css'
import './styles/storm.css'
import './styles/ops-strip.css'
import './styles/whatif.css'

async function resolveFetch(mock: boolean): Promise<FetchLike> {
  if (!mock) return window.fetch.bind(window)
  const { startMock } = await import('./mock')
  const env = await startMock()
  Object.assign(window, { __chhatriMock: env.backend })
  return env.fetch
}

async function boot(): Promise<void> {
  const root = document.getElementById('root')
  if (!root) throw new Error('#root element missing')
  const unknown = unknownFeatures(import.meta.env.VITE_FEATURES)
  if (unknown.length > 0) console.warn('[features] VITE_FEATURES names unknown flags (ignored):', unknown.join(', '))
  const mock = isMockMode(window.location.search, import.meta.env.VITE_MOCK)
  try {
    const api = createApi(new ApiClient(await resolveFetch(mock)))
    createRoot(root).render(
      <StrictMode>
        <App api={api} mock={mock} />
      </StrictMode>,
    )
  } catch (error) {
    console.error('[boot] console failed to start', error)
    root.textContent = 'The Chhatri console failed to start. Check the browser console for details.'
  }
}

void boot()
