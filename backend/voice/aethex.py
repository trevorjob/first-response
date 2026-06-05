import hmac
import hashlib
import os
import time
from typing import Any

import httpx

from voice.base import VoiceProvider, ToolCallPayload, WebhookPayload, TranscriptTurn

_AETHEX_BASE = "https://api.aethexai.com/api/v1"


class AethexProvider(VoiceProvider):
    """
    Voice provider adapter for Aethex AI.

    Tool call body from Aethex:
        { "arguments": {...}, "agent_id": "...", "conversation_id": "co_...", "call_id": "ca_..." }

    Tool response — any JSON; Aethex feeds the whole object to the LLM.

    Webhook envelope:
        { "event": "call.ended"|"transcription.completed", "created_at": "...", "data": {...} }
    Signature header: Aethex-Signature: t=<unix_ts>,v1=<hmac_sha256_hex>
    Signed payload: "<t>.<raw_body>"

    Transcript is NOT in the webhook — fetch separately via GET /conversations/{id}/transcript.
    """

    def __init__(self) -> None:
        self._secret = os.environ.get("AETHEX_WEBHOOK_SECRET", "")
        self._api_key = os.environ.get("AETHEX_API_KEY", "")

    def verify_signature(self, raw_body: bytes, signature_header: str) -> bool:
        if not self._secret:
            return True  # dev mode — no secret configured

        try:
            parts = dict(p.split("=", 1) for p in signature_header.split(","))
            timestamp = parts["t"]
            v1 = parts["v1"]
        except (KeyError, ValueError):
            return False

        if abs(time.time() - int(timestamp)) > 300:
            return False

        signed = f"{timestamp}.{raw_body.decode()}"
        expected = hmac.new(self._secret.encode(), signed.encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(v1, expected)

    def parse_tool_call(self, raw: dict[str, Any]) -> ToolCallPayload:
        return ToolCallPayload(
            tool_name=raw.get("tool_name", ""),
            arguments=raw.get("arguments", {}),
            conversation_id=raw.get("conversation_id", ""),
            call_id=raw.get("call_id", ""),
            agent_id=raw.get("agent_id", ""),
            raw=raw,
        )

    def tool_response(self, incident_id: str, responders_pinged: int,
                      location: str, eta: str) -> dict[str, Any]:
        # Aethex feeds the entire response object to the LLM —
        # use readable key/value pairs so the LLM can narrate them naturally.
        return {
            "status": "dispatched",
            "incident_id": incident_id[:8],
            "responders_alerted": responders_pinged,
            "location": location,
            "estimated_arrival": eta,
            "message": (
                f"Dispatch confirmed. {responders_pinged} responder"
                f"{'s' if responders_pinged != 1 else ''} alerted near {location}. "
                f"Estimated arrival {eta}. Stay on the line."
            ),
        }

    def parse_webhook(self, raw: dict[str, Any]) -> WebhookPayload:
        data = raw.get("data", {})
        return WebhookPayload(
            event=raw.get("event", ""),
            conversation_id=data.get("conversation_id", ""),
            call_id=data.get("call_id", ""),
            transcript=[],   # fetched separately — see fetch_transcript()
            metadata=data,
            raw=raw,
        )

    async def fetch_transcript(self, conversation_id: str) -> list[TranscriptTurn]:
        if not conversation_id or not self._api_key:
            return []
        url = f"{_AETHEX_BASE}/conversations/{conversation_id}/transcript"
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers={"X-API-Key": self._api_key}, timeout=10)
            if resp.status_code != 200:
                return []
            turns = resp.json()
            return [
                TranscriptTurn(role=t.get("role", "unknown"), text=t.get("text", ""))
                for t in turns
                if isinstance(t, dict)
            ]
