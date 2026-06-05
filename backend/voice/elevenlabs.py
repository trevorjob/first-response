import hmac
import hashlib
import os
import time
from typing import Any

from voice.base import VoiceProvider, ToolCallPayload, WebhookPayload, TranscriptTurn


class ElevenLabsProvider(VoiceProvider):
    """
    Voice provider adapter for ElevenLabs Conversational AI (ElevenAgents).

    Tool call body from ElevenLabs:
        {
          "tool_name": "dispatch_emergency",
          "tool_call_id": "call_abc123",
          "parameters": { "emergency_type": "...", ... },
          "conversation_id": "conv_...",
          "agent_id": "agt_..."
        }

    Tool response must be: { "result": "<plain string>" }

    Webhook payload (post_call_transcription event):
        {
          "type": "post_call_transcription",
          "event_timestamp": 1717000000,
          "data": {
            "conversation_id": "conv_...",
            "transcript": [{"role": "agent"|"user", "message": "..."}],
            "analysis": { "transcript_summary": "..." },
            "metadata": { ... }
          }
        }

    Signature header: ElevenLabs-Signature: t=<unix_ts>,v1=<hmac_sha256_hex>
    Signed payload: "<t>.<raw_body>"
    """

    def __init__(self) -> None:
        self._secret = os.environ.get("ELEVENAGENTS_WEBHOOK_SECRET", "")

    def verify_signature(self, raw_body: bytes, signature_header: str) -> bool:
        if not self._secret:
            return True

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
        # ElevenLabs wraps args under "parameters"
        return ToolCallPayload(
            tool_name=raw.get("tool_name", ""),
            arguments=raw.get("parameters", {}),
            conversation_id=raw.get("conversation_id", ""),
            call_id=raw.get("tool_call_id", ""),
            agent_id=raw.get("agent_id", ""),
            raw=raw,
        )

    def tool_response(self, incident_id: str, responders_pinged: int,
                      location: str, eta: str) -> dict[str, Any]:
        # ElevenLabs requires { "result": "<string>" } — agent speaks it verbatim
        return {
            "result": (
                f"Dispatch confirmed. Incident {incident_id[:8]}. "
                f"{responders_pinged} responder{'s' if responders_pinged != 1 else ''} "
                f"alerted near {location}. Estimated arrival {eta}. Stay on the line."
            )
        }

    def parse_webhook(self, raw: dict[str, Any]) -> WebhookPayload:
        event_type = raw.get("type", "")
        data = raw.get("data", raw)

        raw_turns = data.get("transcript", [])
        transcript = [
            TranscriptTurn(
                role=t.get("role", "unknown"),
                text=t.get("message", t.get("content", "")),
            )
            for t in raw_turns
            if isinstance(t, dict)
        ]

        return WebhookPayload(
            event=event_type,
            conversation_id=data.get("conversation_id", ""),
            call_id=data.get("conversation_id", ""),  # ElevenLabs uses conversation_id as call ref
            transcript=transcript,
            metadata=data.get("metadata", {}),
            raw=raw,
        )

    async def fetch_transcript(self, conversation_id: str) -> list[TranscriptTurn]:
        # ElevenLabs includes the transcript in the webhook payload — nothing to fetch
        return []
