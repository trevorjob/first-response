export interface Incident {
  id: string
  created_at: string
  emergency_type: string
  location_text: string
  severity: string
  details: string
  caller_phone: string
  status: 'pending' | 'active' | 'completed' | 'failed'
  assigned_responder_id: string | null
  eta_minutes: number | null
  acknowledged_at: string | null
  transcript: unknown[] | null
  image_url: string | null
  image_insight: string | null
  conversation_id: string | null
  assigned_responder?: Responder | null
}

export interface Responder {
  id: string
  name: string
  phone: string
  type: 'ambulance' | 'fire' | 'first_aid'
  zone: string
  is_available: boolean
  current_incident_id: string | null
  created_at: string
}
