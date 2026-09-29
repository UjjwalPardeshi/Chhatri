import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'

// Initialize mock server if enabled (VITE_USE_MOCKS=1)
if (import.meta.env.VITE_USE_MOCKS) {
  import('./api/mock/server').then((m) => m.initMockServer())
}

import App from './App.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
