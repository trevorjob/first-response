import type { Incident } from '../types'

interface Props {
  incident: Incident
  onClick: () => void
}

const TYPE_ICON: Record<string, string> = { medical: '🚑', fire: '🔥' }
const SEV_COLOR: Record<string, string> = {
  critical: '#ef4444',
  moderate: '#f97316',
  low: '#22c55e',
}
const STATUS_COLOR: Record<string, string> = {
  pending: '#f59e0b',
  active: '#22c55e',
  completed: '#6b7280',
  failed: '#ef4444',
}

function elapsed(iso: string) {
  const s = Math.floor((Date.now() - new Date(iso).getTime()) / 1000)
  if (s < 60) return `${s}s`
  if (s < 3600) return `${Math.floor(s / 60)}m`
  return `${Math.floor(s / 3600)}h ${Math.floor((s % 3600) / 60)}m`
}

export function IncidentCard({ incident, onClick }: Props) {
  return (
    <button className="incident-card" onClick={onClick}>
      <div className="ic-top">
        <span className="ic-icon">{TYPE_ICON[incident.emergency_type] ?? '🚨'}</span>
        <div className="ic-info">
          <div className="ic-type">{incident.emergency_type.toUpperCase()}</div>
          <div className="ic-location">{incident.location_text}</div>
        </div>
        <div className="ic-right">
          <span className="status-dot" style={{ background: STATUS_COLOR[incident.status] }} />
          <span className="ic-status">{incident.status}</span>
        </div>
      </div>
      <div className="ic-bottom">
        <span
          className="sev-badge"
          style={{ background: SEV_COLOR[incident.severity] ?? '#6b7280' }}
        >
          {incident.severity}
        </span>
        <span className="ic-elapsed">{elapsed(incident.created_at)} ago</span>
        {incident.eta_minutes && (
          <span className="ic-eta">ETA {incident.eta_minutes}m</span>
        )}
      </div>
    </button>
  )
}
