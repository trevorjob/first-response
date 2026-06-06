import asyncio
import json
import os
from fastapi import APIRouter, Depends, Request, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models.incident import Incident
from models.responder import Responder
from models.ping_log import PingLog
from services.twilio_service import send_sms_bulk, build_responder_sms
from voice import get_provider

router = APIRouter()

# incident_id -> asyncio Task for the 90s re-ping loop
_ping_tasks: dict[str, asyncio.Task] = {}


@router.post("/dispatch")
async def dispatch_emergency(request: Request, db: Session = Depends(get_db)):
    raw = await request.body()
    provider = get_provider()

    sig = request.headers.get("Aethex-Signature", "") or request.headers.get("ElevenLabs-Signature", "")
    if sig and not provider.verify_signature(raw, sig):
        raise HTTPException(status_code=401, detail="Invalid signature")

    payload = json.loads(raw)
    tool_call = provider.parse_tool_call(payload)
    args = tool_call.arguments

    emergency_type = args.get("emergency_type", "medical")
    location = args.get("location", "")
    severity = args.get("severity", "moderate")
    details = args.get("details", "")
    caller_phone = args.get("caller_phone", "")

    if not location:
        raise HTTPException(status_code=422, detail="location is required")

    # Agent sends "medical" or "fire"; DB stores "ambulance", "fire", "first_aid"
    RESPONDER_TYPES: dict[str, list[str]] = {
        "medical": ["ambulance", "first_aid"],
        "fire":    ["fire"],
    }
    responder_types = RESPONDER_TYPES.get(emergency_type, [emergency_type])

    incident = Incident(
        emergency_type=emergency_type,
        location_text=location,
        severity=severity,
        details=details,
        caller_phone=caller_phone,
        conversation_id=tool_call.conversation_id,
        status="pending",
    )
    db.add(incident)
    db.commit()
    db.refresh(incident)

    zone_prefix = location.split(',')[0].strip()

    # Zone match first, fall back to type-only
    responders = (
        db.query(Responder)
        .filter(
            Responder.type.in_(responder_types),
            Responder.zone.ilike(f"%{zone_prefix}%"),
            Responder.is_available == True,
        )
        .limit(3)
        .all()
    )
    if not responders:
        responders = (
            db.query(Responder)
            .filter(Responder.type.in_(responder_types), Responder.is_available == True)
            .limit(3)
            .all()
        )

    frontend_url = os.environ.get("FRONTEND_URL", os.environ.get("APP_URL", "http://localhost:5173"))
    sms_batch = [(r.phone, build_responder_sms(incident, r, frontend_url)) for r in responders]
    await send_sms_bulk(sms_batch)

    for r in responders:
        db.add(PingLog(incident_id=incident.id, responder_id=r.id, acknowledged=False))
    db.commit()

    incident_id_str = str(incident.id)
    task = asyncio.create_task(
        _ping_loop(incident_id_str, [str(r.id) for r in responders], frontend_url)
    )
    _ping_tasks[incident_id_str] = task

    return provider.tool_response(
        incident_id=incident_id_str,
        responders_pinged=len(responders),
        location=location,
        eta="8 to 12 minutes",
    )


async def _ping_loop(incident_id: str, responder_ids: list[str], app_url: str):
    await asyncio.sleep(90)
    from database import SessionLocal
    while True:
        db = SessionLocal()
        try:
            incident = db.query(Incident).filter(Incident.id == incident_id).first()
            if not incident or incident.status != "pending":
                return
            batch = []
            for rid in responder_ids:
                r = db.query(Responder).filter(Responder.id == rid).first()
                if r:
                    batch.append((r.phone, build_responder_sms(incident, r, app_url)))
                    db.add(PingLog(incident_id=incident.id, responder_id=r.id, acknowledged=False))
            await send_sms_bulk(batch)
            db.commit()
        finally:
            db.close()
        await asyncio.sleep(90)


def cancel_ping_loop(incident_id: str):
    task = _ping_tasks.pop(incident_id, None)
    if task:
        task.cancel()
