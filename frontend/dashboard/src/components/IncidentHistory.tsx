import { useState } from 'react'
import type { Incident } from '../types'

interface Props {
  incidents: Incident[]
  onSelect: (incident: Incident) => void
}

export function IncidentHistory({ incidents, onSelect }: Props) {
  const [typeFilter, setTypeFilter] = useState('all')
  const [dateFilter, setDateFilter] = useState('')

  const completed = incidents.filter(i => i.status === 'completed' || i.status === 'failed')

  const filtered = completed.filter(i => {
    if (typeFilter !== 'all' && i.emergency_type !== typeFilter) return false
    if (dateFilter) {
      const d = new Date(i.created_at).toISOString().slice(0, 10)
      if (d !== dateFilter) return false
    }
    return true
  })

  return (
    <div className="history">
      <div className="history-toolbar">
        <select
          className="filter-select"
          value={typeFilter}
          onChange={e => setTypeFilter(e.target.value)}
        >
          <option value="all">All types</option>
          <option value="medical">Medical</option>
          <option value="fire">Fire</option>
        </select>
        <input
          type="date"
          className="filter-date"
          value={dateFilter}
          onChange={e => setDateFilter(e.target.value)}
        />
        {(typeFilter !== 'all' || dateFilter) && (
          <button className="clear-filter" onClick={() => { setTypeFilter('all'); setDateFilter('') }}>
            Clear
          </button>
        )}
        <span className="registry-count">{filtered.length} incidents</span>
      </div>

      <div className="table-wrap">
        <table className="responder-table">
          <thead>
            <tr>
              <th>Time</th>
              <th>Type</th>
              <th>Location</th>
              <th>Severity</th>
              <th>Status</th>
              <th>ETA</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map(i => (
              <tr key={i.id} className="history-row" onClick={() => onSelect(i)}>
                <td className="muted">{new Date(i.created_at).toLocaleString()}</td>
                <td>{i.emergency_type}</td>
                <td>{i.location_text}</td>
                <td>{i.severity}</td>
                <td>
                  <span className={`status-chip status-${i.status}`}>{i.status}</span>
                </td>
                <td>{i.eta_minutes ? `${i.eta_minutes}m` : '—'}</td>
              </tr>
            ))}
            {filtered.length === 0 && (
              <tr>
                <td colSpan={6} className="empty-row">No completed incidents</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
