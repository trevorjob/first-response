import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import AcknowledgePage from './AcknowledgePage.tsx'

const isAckPage = window.location.pathname === '/respond'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    {isAckPage ? <AcknowledgePage /> : <App />}
  </StrictMode>,
)
