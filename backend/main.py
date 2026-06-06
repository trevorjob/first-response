import os
import logging
logging.basicConfig(level=logging.INFO)
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from database import engine, Base
from models import Incident, Responder, PingLog
from routes import dispatch, acknowledge, analyze_image, incident_report
from routes import incidents, responders, whatsapp

logger = logging.getLogger(__name__)


async def _sync_aethex_urls():
    app_url = os.environ.get("APP_URL", "").rstrip("/")
    agent_id_file = os.path.join(os.path.dirname(__file__), ".aethex_agent_id")

    if not app_url or not os.path.isfile(agent_id_file):
        return

    try:
        from aethexai import AethexAI
        from pathlib import Path

        agent_id = Path(agent_id_file).read_text().strip()
        client = AethexAI(api_key=os.environ["AETHEX_API_KEY"])
        tools = client.list_agent_tools(agent_id)

        URL_MAP = {
            "dispatch_emergency": f"{app_url}/dispatch",
            "send_whatsapp_prompt": f"{app_url}/send-whatsapp",
            "check_scene_image": f"{app_url}/check-scene-image",
        }

        for tool in tools:
            t = tool if isinstance(tool, dict) else vars(tool)
            name = t.get("name", "")
            tool_id = t.get("id", "")
            if name in URL_MAP:
                client.update_agent_tool(agent_id, tool_id, endpoint_url=URL_MAP[name])
                logger.info(f"Aethex tool '{name}' → {URL_MAP[name]}")

        logger.info("Aethex tool URLs synced to %s", app_url)
    except Exception as e:
        logger.warning("Aethex URL sync failed (non-fatal): %s", e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await _sync_aethex_urls()
    yield


Base.metadata.create_all(bind=engine)

app = FastAPI(title="First Response API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(dispatch.router)
app.include_router(acknowledge.router)
app.include_router(analyze_image.router)
app.include_router(incident_report.router)
app.include_router(incidents.router)
app.include_router(responders.router)
app.include_router(whatsapp.router)


@app.get("/health")
def health():
    return {"status": "ok"}


# Serve React frontend — must come last so API routes take priority
_frontend_dist = os.path.join(os.path.dirname(__file__), "..", "frontend", "dashboard", "dist")
if os.path.isdir(_frontend_dist):
    app.mount("/assets", StaticFiles(directory=os.path.join(_frontend_dist, "assets")), name="assets")

    @app.get("/{full_path:path}")
    def spa_fallback(full_path: str):
        index = os.path.join(_frontend_dist, "index.html")
        return FileResponse(index)
