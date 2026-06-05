import { useState } from 'react'
import type { Responder } from '../types'

interface Props {
  responders: Responder[]
  onToggle: (id: string, available: boolean) => void
}

const TYPE_ICON: Record<string, string> = {
  ambulance: '🚑',
  fire: '🔥',
  first_aid: '🩺',
}

export function ResponderRegistry({ responders, onToggle }: Props) {
  const [filter, setFilter] = useState<string>('all')

  const filtered = filter === 'all' ? responders : responders.filter(r => r.type === filter)

  return (
    <div className="registry">
      <div className="registry-toolbar">
        <div className="filter-tabs">
          {['all', 'ambulance', 'fire', 'first_aid'].map(t => (
            <button
              key={t}
              className={`filter-tab ${filter === t ? 'active' : ''}`}
              onClick={() => setFilter(t)}
            >
              {t === 'all' ? 'All' : `${TYPE_ICON[t]} ${t}`}
            </button>
          ))}
        </div>
        <span className="registry-count">{filtered.length} responders</span>
      </div>

      <div className="table-wrap">
        <table className="responder-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Type</th>
              <th>Zone</th>
              <th>Phone</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map(r => (
              <tr key={r.id}>
                <td className="td-name">{r.name}</td>
                <td>{TYPE_ICON[r.type]} {r.type}</td>
                <td className="muted">{r.zone}</td>
                <td>
                  <a href={`tel:${r.phone}`} className="phone-link">{r.phone}</a>
                </td>
                <td>
                  <button
                    className={`avail-toggle ${r.is_available ? 'available' : 'unavailable'}`}
                    onClick={() => onToggle(r.id, !r.is_available)}
                  >
                    {r.is_available ? 'Available' : 'Busy'}
                  </button>
                </td>
              </tr>
            ))}
            {filtered.length === 0 && (
              <tr>
                <td colSpan={5} className="empty-row">No responders found</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
