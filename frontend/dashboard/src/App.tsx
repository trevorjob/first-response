import { useState, useCallback } from 'react'
import type { Incident, Responder } from './types'
import { usePolling } from './hooks/usePolling'
import { IncidentCard } from './components/IncidentCard'
import { IncidentModal } from './components/IncidentModal'
import { ResponderRegistry } from './components/ResponderRegistry'
import { IncidentHistory } from './components/IncidentHistory'
import './App.css'

type Tab = 'active' | 'responders' | 'history'

const API = import.meta.env.VITE_API_URL ?? ''

async function apiFetch<T>(path: string): Promise<T> {
  const res = await fetch(`${API}${path}`)
  if (!res.ok) throw new Error(`${res.status}`)
  return res.json() as Promise<T>
}

export default function App() {
  const [tab, setTab] = useState<Tab>('active')
  const [incidents, setIncidents] = useState<Incident[]>([])
  const [responders, setResponders] = useState<Responder[]>([])
  const [selected, setSelected] = useState<Incident | null>(null)
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null)

  const fetchIncidents = useCallback(async () => {
    try {
      const data = await apiFetch<Incident[]>('/incidents')
      setIncidents(data)
      setLastUpdated(new Date())
    } catch { /* silent — will retry */ }
  }, [])

  const fetchResponders = useCallback(async () => {
    try {
      const data = await apiFetch<Responder[]>('/responders')
      setResponders(data)
    } catch { /* silent */ }
  }, [])

  usePolling(fetchIncidents, 5000)
  usePolling(fetchResponders, 10000)

  const active = incidents.filter(i => i.status === 'pending' || i.status === 'active')

  async function toggleAvailability(id: string, available: boolean) {
    try {
      await fetch(`${API}/responders/${id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ is_available: available }),
      })
      setResponders(prev =>
        prev.map(r => r.id === id ? { ...r, is_available: available } : r)
      )
    } catch { /* silent */ }
  }

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="logo">
          <span className="logo-mark">FR</span>
          <span className="logo-text">First Response</span>
        </div>

        <nav className="nav">
          <button
            className={`nav-item ${tab === 'active' ? 'active' : ''}`}
            onClick={() => setTab('active')}
          >
            <span className="nav-icon">🚨</span>
            <span>Active Incidents</span>
            {active.length > 0 && <span className="nav-badge">{active.length}</span>}
          </button>
          <button
            className={`nav-item ${tab === 'responders' ? 'active' : ''}`}
            onClick={() => setTab('responders')}
          >
            <span className="nav-icon">👥</span>
            <span>Responders</span>
          </button>
          <button
            className={`nav-item ${tab === 'history' ? 'active' : ''}`}
            onClick={() => setTab('history')}
          >
            <span className="nav-icon">📋</span>
            <span>History</span>
          </button>
        </nav>

        <div className="sidebar-footer">
          {lastUpdated && (
            <span className="last-updated">
              Updated {lastUpdated.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
            </span>
          )}
          <span className="pulse-dot" title="Live polling" />
        </div>
      </aside>

      <main className="content">
        {tab === 'active' && (
          <div className="panel">
            <div className="panel-header">
              <h1 className="panel-title">Active Incidents</h1>
              <span className="panel-count">{active.length} open</span>
            </div>
            {active.length === 0 ? (
              <div className="empty-state">
                <div className="empty-icon">✅</div>
                <div>No active incidents</div>
              </div>
            ) : (
              <div className="incident-feed">
                {active.map(i => (
                  <IncidentCard key={i.id} incident={i} onClick={() => setSelected(i)} />
                ))}
              </div>
            )}
          </div>
        )}

        {tab === 'responders' && (
          <div className="panel">
            <div className="panel-header">
              <h1 className="panel-title">Responder Registry</h1>
              <span className="panel-count">
                {responders.filter(r => r.is_available).length} available
              </span>
            </div>
            <ResponderRegistry responders={responders} onToggle={toggleAvailability} />
          </div>
        )}

        {tab === 'history' && (
          <div className="panel">
            <div className="panel-header">
              <h1 className="panel-title">Incident History</h1>
            </div>
            <IncidentHistory
              incidents={incidents}
              onSelect={i => setSelected(i)}
            />
          </div>
        )}
      </main>

      {selected && (
        <IncidentModal incident={selected} onClose={() => setSelected(null)} />
      )}
    </div>
  )
}
