import os
from voice.base import VoiceProvider


def get_provider() -> VoiceProvider:
    """
    Return the active voice provider based on VOICE_PROVIDER env var.
    Set VOICE_PROVIDER=aethex  to use Aethex AI (default).
    Set VOICE_PROVIDER=elevenlabs  to use ElevenLabs Conversational AI.
    """
    provider = os.environ.get("VOICE_PROVIDER", "aethex").lower().strip()

    if provider == "elevenlabs":
        from voice.elevenlabs import ElevenLabsProvider
        return ElevenLabsProvider()

    from voice.aethex import AethexProvider
    return AethexProvider()
