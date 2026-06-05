import json
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session
from database import get_db
from models.incident import Incident
from services.openai_service import generate_incident_summary
from voice import get_provider

router = APIRouter()


class IncidentReportResponse(BaseModel):
    status: str
    incident_id: str


@router.post("/incident-report", response_model=IncidentReportResponse)
async def incident_report(request: Request, db: Session = Depends(get_db)):
    raw = await request.body()
    provider = get_provider()

    sig = request.headers.get("Aethex-Signature", "") or request.headers.get("ElevenLabs-Signature", "")
    if sig and not provider.verify_signature(raw, sig):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    payload = json.loads(raw)

    # Handle liveness pings from either provider
    event_type = payload.get("event", "") or payload.get("type", "")
    if event_type in ("ping", ""):
        return IncidentReportResponse(status="pong", incident_id="")

    webhook = provider.parse_webhook(payload)

    # If transcript is empty, provider requires a separate fetch (Aethex)
    transcript = webhook.transcript
    if not transcript and webhook.conversation_id:
        transcript = await provider.fetch_transcript(webhook.conversation_id)

    # Match incident by conversation_id, fall back to most recent active
    incident = None
    if webhook.conversation_id:
        incident = (
            db.query(Incident)
            .filter(Incident.conversation_id == webhook.conversation_id)
            .first()
        )
    if not incident:
        incident = (
            db.query(Incident)
            .filter(Incident.status.in_(["pending", "active"]))
            .order_by(Incident.created_at.desc())
            .first()
        )
    if not incident:
        raise HTTPException(status_code=404, detail="No matching incident for this conversation")

    # Store transcript as list of dicts for JSON serialisation
    incident.transcript = [{"role": t.role, "text": t.text} for t in transcript]
    incident.conversation_id = webhook.conversation_id
    incident.status = "completed"

    # Use ElevenLabs summary if present, otherwise generate via OpenAI
    summary = (
        webhook.raw.get("data", {}).get("analysis", {}).get("transcript_summary", "")
        if event_type == "post_call_transcription"
        else ""
    )
    if not summary and transcript:
        raw_turns = [{"role": t.role, "message": t.text} for t in transcript]
        summary = await generate_incident_summary(raw_turns, webhook.metadata)

    if summary:
        incident.details = (
            summary if not incident.details
            else f"{incident.details}\n\n--- AI Summary ---\n{summary}"
        )

    db.commit()

    return IncidentReportResponse(status="saved", incident_id=str(incident.id))
