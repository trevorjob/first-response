import { useEffect } from 'react'
import type { Incident } from '../types'

interface Props {
  incident: Incident
  onClose: () => void
}

function fmt(iso: string) {
  return new Date(iso).toLocaleString()
}

export function IncidentModal({ incident, onClose }: Props) {
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  const transcript = incident.transcript as { role?: string; message?: string; content?: string }[] | null

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <div>
            <div className="modal-title">
              {incident.emergency_type.toUpperCase()} — {incident.location_text}
            </div>
            <div className="modal-sub">
              {fmt(incident.created_at)} · {incident.caller_phone ?? 'Unknown caller'}
            </div>
          </div>
          <button className="close-btn" onClick={onClose}>✕</button>
        </div>

        <div className="modal-body">
          <div className="modal-grid">
            <div className="detail-block">
              <div className="detail-label">Status</div>
              <div className="detail-value">{incident.status}</div>
            </div>
            <div className="detail-block">
              <div className="detail-label">Severity</div>
              <div className="detail-value">{incident.severity}</div>
            </div>
            <div className="detail-block">
              <div className="detail-label">ETA</div>
              <div className="detail-value">{incident.eta_minutes ? `${incident.eta_minutes} min` : '—'}</div>
            </div>
            <div className="detail-block">
              <div className="detail-label">Acknowledged</div>
              <div className="detail-value">{incident.acknowledged_at ? fmt(incident.acknowledged_at) : '—'}</div>
            </div>
          </div>

          {incident.assigned_responder && (
            <div className="section">
              <div className="section-title">Assigned Responder</div>
              <div className="responder-row">
                <span>{incident.assigned_responder.name}</span>
                <span className="muted">{incident.assigned_responder.type} · {incident.assigned_responder.zone}</span>
                <a href={`tel:${incident.assigned_responder.phone}`} className="phone-link">
                  {incident.assigned_responder.phone}
                </a>
              </div>
            </div>
          )}

          {incident.details && (
            <div className="section">
              <div className="section-title">Details</div>
              <p className="section-text">{incident.details}</p>
            </div>
          )}

          {incident.image_url && (
            <div className="section">
              <div className="section-title">Scene Photo</div>
              <img src={incident.image_url} alt="Scene" className="scene-img" />
              {incident.image_insight && (
                <div className="insight-box">
                  <span className="insight-label">AI Insight</span>
                  <p>{incident.image_insight}</p>
                </div>
              )}
            </div>
          )}

          {transcript && transcript.length > 0 && (
            <div className="section">
              <div className="section-title">Transcript</div>
              <div className="transcript">
                {transcript.map((t, i) => (
                  <div key={i} className={`transcript-line ${t.role ?? ''}`}>
                    <span className="t-role">{t.role ?? 'unknown'}</span>
                    <span className="t-msg">{t.message ?? t.content ?? ''}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
