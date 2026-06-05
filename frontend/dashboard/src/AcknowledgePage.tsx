import { useState, useEffect } from 'react'
import './AcknowledgePage.css'

type State = 'loading' | 'ready' | 'submitting' | 'confirmed' | 'error' | 'already_handled'

interface IncidentInfo {
  emergency_type: string
  location_text: string
  severity: string
  details: string
  caller_phone: string
  created_at: string
  status: string
}

const API_BASE = import.meta.env.VITE_API_URL ?? ''

const SEVERITY_COLOR: Record<string, string> = {
  critical: '#ef4444',
  moderate: '#f97316',
  low: '#22c55e',
}

const TYPE_ICON: Record<string, string> = {
  medical: '🚑',
  fire: '🔥',
}

function formatTime(iso: string) {
  return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

function minutesAgo(iso: string) {
  const diff = Math.floor((Date.now() - new Date(iso).getTime()) / 60000)
  if (diff < 1) return 'just now'
  return `${diff}m ago`
}

export default function AcknowledgePage() {
  const params = new URLSearchParams(window.location.search)
  const incidentId = params.get('incident_id') ?? ''
  const responderId = params.get('responder_id') ?? ''

  const [state, setState] = useState<State>(!incidentId || !responderId ? 'error' : 'loading')
  const [incident, setIncident] = useState<IncidentInfo | null>(null)
  const [eta, setEta] = useState('8')
  const [errorMsg, setErrorMsg] = useState(
    !incidentId || !responderId ? 'Invalid link — missing incident or responder ID.' : ''
  )

  useEffect(() => {
    if (!incidentId || !responderId) return
    fetch(`${API_BASE}/incident/${incidentId}`)
      .then(r => r.json())
      .then((data: IncidentInfo) => {
        if (data.status === 'active' || data.status === 'completed') {
          setState('already_handled')
        } else {
          setIncident(data)
          setState('ready')
        }
      })
      .catch(() => setState('ready'))
  }, [incidentId, responderId])

  async function handleConfirm() {
    const etaNum = parseInt(eta, 10)
    if (!etaNum || etaNum < 1) return
    setState('submitting')
    try {
      const res = await fetch(`${API_BASE}/acknowledge`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ incident_id: incidentId, responder_id: responderId, eta_minutes: etaNum }),
      })
      if (!res.ok) throw new Error(await res.text())
      setState('confirmed')
    } catch (e: unknown) {
      setErrorMsg(e instanceof Error ? e.message : 'Something went wrong.')
      setState('error')
    }
  }

  if (state === 'loading') {
    return <div className="page center"><div className="spinner" /></div>
  }

  if (state === 'already_handled') {
    return (
      <div className="page center">
        <div className="card">
          <div className="icon-lg">✅</div>
          <h2>Already Confirmed</h2>
          <p className="muted">A responder has already acknowledged this incident.</p>
        </div>
      </div>
    )
  }

  if (state === 'confirmed') {
    return (
      <div className="page center">
        <div className="card">
          <div className="icon-lg">✅</div>
          <h2>Confirmed</h2>
          <p>Dispatch notified. You are en route.</p>
          <p className="muted eta-confirm">ETA: <strong>{eta} minutes</strong></p>
        </div>
      </div>
    )
  }

  if (state === 'error') {
    return (
      <div className="page center">
        <div className="card error-card">
          <div className="icon-lg">⚠️</div>
          <h2>Error</h2>
          <p className="muted">{errorMsg}</p>
        </div>
      </div>
    )
  }

  const sevColor = SEVERITY_COLOR[incident?.severity ?? ''] ?? '#6b7280'
  const typeIcon = TYPE_ICON[incident?.emergency_type ?? ''] ?? '🚨'

  return (
    <div className="page">
      <header className="header">
        <span className="brand">FIRST RESPONSE</span>
        <span className="dispatch-badge">DISPATCH</span>
      </header>

      <main className="main">
        <div className="card incident-card">
          <div className="incident-header">
            <span className="type-icon">{typeIcon}</span>
            <div className="incident-meta">
              <div className="type-label">{incident?.emergency_type?.toUpperCase() ?? 'EMERGENCY'}</div>
              <div className="severity-badge" style={{ background: sevColor }}>
                {incident?.severity?.toUpperCase() ?? '—'}
              </div>
            </div>
            {incident?.created_at && (
              <div className="time-info">
                <div>{formatTime(incident.created_at)}</div>
                <div className="muted">{minutesAgo(incident.created_at)}</div>
              </div>
            )}
          </div>

          <div className="field">
            <span className="label">Location</span>
            <span className="value">{incident?.location_text ?? '—'}</span>
          </div>

          {incident?.details && (
            <div className="field">
              <span className="label">Details</span>
              <span className="value">{incident.details}</span>
            </div>
          )}

          {incident?.caller_phone && (
            <div className="field">
              <span className="label">Caller</span>
              <span className="value">
                <a href={`tel:${incident.caller_phone}`}>{incident.caller_phone}</a>
              </span>
            </div>
          )}
        </div>

        <div className="eta-block">
          <label htmlFor="eta" className="eta-label">I will arrive in</label>
          <div className="eta-row">
            <input
              id="eta"
              type="number"
              min="1"
              max="120"
              value={eta}
              onChange={e => setEta(e.target.value)}
              className="eta-input"
            />
            <span className="eta-unit">minutes</span>
          </div>
        </div>

        <button
          className="confirm-btn"
          onClick={handleConfirm}
          disabled={state === 'submitting'}
        >
          {state === 'submitting' ? 'Confirming...' : 'I am on my way'}
        </button>
      </main>
    </div>
  )
}
