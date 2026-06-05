from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import datetime
from database import get_db
from models.incident import Incident
from models.responder import Responder
from models.ping_log import PingLog

router = APIRouter()


class AcknowledgeRequest(BaseModel):
    incident_id: str
    responder_id: str
    eta_minutes: int


class AcknowledgeResponse(BaseModel):
    status: str
    incident_id: str
    eta_minutes: int


@router.post("/acknowledge", response_model=AcknowledgeResponse)
def acknowledge_incident(body: AcknowledgeRequest, db: Session = Depends(get_db)):
    incident = db.query(Incident).filter(Incident.id == body.incident_id).first()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    if incident.status not in ("pending",):
        raise HTTPException(status_code=400, detail=f"Incident already {incident.status}")

    incident.status = "active"
    incident.assigned_responder_id = body.responder_id
    incident.eta_minutes = body.eta_minutes
    incident.acknowledged_at = datetime.utcnow()

    responder = db.query(Responder).filter(Responder.id == body.responder_id).first()
    if responder:
        responder.is_available = False
        responder.current_incident_id = incident.id

    ping = (
        db.query(PingLog)
        .filter(PingLog.incident_id == body.incident_id, PingLog.responder_id == body.responder_id)
        .order_by(PingLog.sent_at.desc())
        .first()
    )
    if ping:
        ping.acknowledged = True

    db.commit()

    from routes.dispatch import cancel_ping_loop
    cancel_ping_loop(body.incident_id)

    return AcknowledgeResponse(
        status="acknowledged",
        incident_id=body.incident_id,
        eta_minutes=body.eta_minutes,
    )
