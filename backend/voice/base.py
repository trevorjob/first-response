from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class ToolCallPayload:
    """Normalised tool call from any voice provider."""
    tool_name: str
    arguments: dict[str, Any]
    conversation_id: str
    call_id: str
    agent_id: str
    raw: dict[str, Any]


@dataclass
class TranscriptTurn:
    role: str   # "agent" | "user"
    text: str


@dataclass
class WebhookPayload:
    """Normalised post-call webhook from any voice provider."""
    event: str              # "call.ended" | "transcription.completed" | etc.
    conversation_id: str
    call_id: str
    transcript: list[TranscriptTurn]
    metadata: dict[str, Any]
    raw: dict[str, Any]


class VoiceProvider(ABC):
    """
    Adapter interface for a voice AI provider.
    Implement this for each provider (Aethex, ElevenLabs, etc.).
    Routes import get_provider() and work against this interface.
    """

    @abstractmethod
    def verify_signature(self, raw_body: bytes, signature_header: str) -> bool:
        """Return True if the request is authentically from this provider."""

    @abstractmethod
    def parse_tool_call(self, raw: dict[str, Any]) -> ToolCallPayload:
        """Parse a raw tool call POST body into a normalised ToolCallPayload."""

    @abstractmethod
    def tool_response(self, incident_id: str, responders_pinged: int,
                      location: str, eta: str) -> dict[str, Any]:
        """Build the JSON response body the provider expects back from a tool call."""

    @abstractmethod
    def parse_webhook(self, raw: dict[str, Any]) -> WebhookPayload:
        """Parse a raw post-call webhook body into a normalised WebhookPayload."""

    @abstractmethod
    async def fetch_transcript(self, conversation_id: str) -> list[TranscriptTurn]:
        """
        Fetch the turn-by-turn transcript for a completed conversation.
        Some providers include it in the webhook; others require a separate API call.
        """
