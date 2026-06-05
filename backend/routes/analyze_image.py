import json
import uuid
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import cast, Text
from sqlalchemy.orm import Session
from database import get_db
from models.incident import Incident
from services.openai_service import analyze_scene_image

router = APIRouter()


class AnalyzeImageRequest(BaseModel):
    image_url: str
    incident_id: str
    media_type: str = "image/jpeg"


class AnalyzeImageResponse(BaseModel):
    insight: str
    incident_id: str


@router.post("/analyze-image", response_model=AnalyzeImageResponse)
async def analyze_image(body: AnalyzeImageRequest, db: Session = Depends(get_db)):
    incident = db.query(Incident).filter(Incident.id == body.incident_id).first()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    insight = await analyze_scene_image(body.image_url)
    incident.image_url = body.image_url
    incident.image_insight = insight
    db.commit()

    return AnalyzeImageResponse(insight=insight, incident_id=body.incident_id)


@router.post("/check-scene-image")
async def check_scene_image(request: Request, db: Session = Depends(get_db)):
    """
    Agent calls this tool mid-call to poll for the WhatsApp scene photo insight.
    Returns the GPT-4o analysis once the photo has been processed, or a
    not_ready message telling the agent to retry in ~15 seconds.

    Aethex tool call body: { "arguments": { "incident_id": "..." }, ... }
    """
    raw = await request.body()
    payload = json.loads(raw) if raw else {}
    args = payload.get("arguments", payload)
    incident_id = args.get("incident_id", "")

    if not incident_id:
        return {"status": "error", "message": "incident_id is required"}

    try:
        uuid.UUID(incident_id)
        incident = db.query(Incident).filter(Incident.id == incident_id).first()
    except ValueError:
        incident = (
            db.query(Incident)
            .filter(cast(Incident.id, Text).like(f"{incident_id}%"))
            .order_by(Incident.created_at.desc())
            .first()
        )
    if not incident:
        return {"status": "error", "message": "Incident not found"}

    if incident.image_insight:
        return {
            "status": "ready",
            "insight": incident.image_insight,
            "message": incident.image_insight,
        }

    return {
        "status": "not_ready",
        "message": "Photo not received yet. Please ask the caller to send the photo now, then check again in 15 seconds.",
    }
