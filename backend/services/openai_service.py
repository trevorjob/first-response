import os
import base64
import httpx
from openai import AsyncOpenAI

_client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

VISION_SYSTEM_PROMPT = (
    "You are an emergency response AI. Analyze this scene photo and provide a concise "
    "(2-3 sentence) assessment for a caller. Focus on: visible injuries or hazards, "
    "immediate actions the caller should take, any safety concerns. "
    "Be direct and calm. Do not speculate beyond what is visible."
)

REPORT_SYSTEM_PROMPT = (
    "You are an emergency dispatch AI. Given a call transcript, extract a structured "
    "incident summary. Include: emergency type, location, key details, outcome, and any "
    "notable events during the call. Be concise and factual."
)


async def analyze_scene_image(image_url: str) -> str:
    async with httpx.AsyncClient() as http:
        response = await http.get(image_url)
        response.raise_for_status()
        image_b64 = base64.b64encode(response.content).decode("utf-8")
        content_type = response.headers.get("content-type", "image/jpeg").split(";")[0]

    result = await _client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": VISION_SYSTEM_PROMPT},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{content_type};base64,{image_b64}"},
                    },
                ],
            }
        ],
        max_tokens=300,
    )
    return result.choices[0].message.content.strip()


async def generate_incident_summary(transcript: list, metadata: dict) -> str:
    transcript_text = "\n".join(
        f"{t.get('role', 'unknown').upper()}: {t.get('message', t.get('content', ''))}"
        for t in transcript
        if isinstance(t, dict)
    )

    result = await _client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": REPORT_SYSTEM_PROMPT},
            {"role": "user", "content": f"Transcript:\n{transcript_text}"},
        ],
        max_tokens=500,
    )
    return result.choices[0].message.content.strip()
