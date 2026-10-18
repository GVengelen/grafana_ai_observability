import json
import re

from anthropic import AsyncAnthropic

from app.core.config import settings


SYSTEM_PROMPT = (
    "You generate one concise trivia question about the given subject and provide the exact answer and short explanation. "
    "If the subject is a Pokemon, focus on Pokemon characteristics. For any other subject, ask a factual question about it. "
    "Output ONLY raw JSON with keys: prompt, answer, explanation. "
    "Do not wrap the JSON in markdown code fences or any other text."
)


def _extract_json(text: str) -> dict:
    """Strip optional markdown code fences then parse JSON."""
    text = text.strip()
    # Remove ```json ... ``` or ``` ... ``` wrappers if present
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return json.loads(text.strip())


async def generate_question_from_context(context: dict, is_subject_only: bool = False) -> dict:
    # No-op for local development when no API key is set.
    if not settings.anthropic_api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not configured")

    anthropic_client = AsyncAnthropic(api_key=settings.anthropic_api_key, timeout=settings.anthropic_timeout_seconds)

    request = {
        "model": settings.anthropic_model,
        "max_tokens": 250,
        "system": SYSTEM_PROMPT,
        "messages": [
            {
                "role": "user",
                "content": (
                    f"Ask a question about: {context['name']}"
                    if is_subject_only
                    else f"Create a Pokemon trivia question based on this context: {context}. Output JSON only."
                ),
            }
        ],
    }

    message = await anthropic_client.messages.create(**request)

    text = ""
    for block in message.content:
        if getattr(block, "type", None) == "text":
            text += block.text

    return _extract_json(text)
