import asyncio
import json
import logging
from typing import Any

from google import genai
from google.genai.types import GenerateContentConfig

from app.config import get_settings
from app.exceptions import AIServiceError
from app.services.ai.base import AIProvider

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 1.0
# Grounding: deterministic generation anchored strictly on the provided content.
TEMPERATURE = 0.0


class GeminiProvider(AIProvider):
    def __init__(self, api_key: str, model: str | list[str]):
        self.client = genai.Client(api_key=api_key)
        if isinstance(model, str):
            self.models = [model]
        else:
            self.models = list(model) or ["gemini-3.6-flash"]
        self.model = self.models[0]

    async def generate_text(self, prompt: str, system_prompt: str = "") -> str:
        response = await self._call_with_retry(
            self.client.aio.models.generate_content,
            contents=prompt,
            config=GenerateContentConfig(
                system_instruction=system_prompt or None,
                temperature=TEMPERATURE,
            ),
        )
        return response.text

    async def generate_structured_json(
        self, prompt: str, system_prompt: str = ""
    ) -> dict[str, Any]:
        response = await self._call_with_retry(
            self.client.aio.models.generate_content,
            contents=prompt,
            config=GenerateContentConfig(
                system_instruction=system_prompt or None,
                temperature=TEMPERATURE,
                response_mime_type="application/json",
            ),
        )
        try:
            return json.loads(response.text)
        except (json.JSONDecodeError, TypeError) as exc:
            logger.error("Failed to parse structured JSON from model: %s", exc)
            raise AIServiceError("AI returned invalid JSON") from exc

    @staticmethod
    def _is_model_unavailable(exc: Exception) -> bool:
        """Quota exhaustion (RESOURCE_EXHAUSTED) and retired models (NOT_FOUND)
        are not cured by retrying the same model, so a fallback is needed.
        Reads the real attributes of google.genai APIError."""
        status = getattr(exc, "status", None)
        if status in ("RESOURCE_EXHAUSTED", "NOT_FOUND"):
            return True
        if status is None:
            code = getattr(exc, "code", None)
            if code == 404:
                return True
            if code == 429:
                details = getattr(exc, "details", None) or {}
                if (
                    isinstance(details, dict)
                    and details.get("status") == "RESOURCE_EXHAUSTED"
                ):
                    return True
        return False

    async def _call_with_retry(self, func, *args, **kwargs) -> Any:
        last_error: Exception | None = None
        for model in self.models:
            for attempt in range(MAX_RETRIES):
                try:
                    kwargs["model"] = model
                    return await func(*args, **kwargs)
                except Exception as exc:
                    last_error = exc
                    if self._is_model_unavailable(exc):
                        logger.warning(
                            "Model %s unavailable (%s); switching to next model",
                            model,
                            exc,
                        )
                        break
                    if attempt < MAX_RETRIES - 1:
                        delay = RETRY_DELAY_SECONDS * (2**attempt)
                        logger.warning(
                            "AI call failed (attempt %d/%d): %s. Retrying in %.1fs",
                            attempt + 1,
                            MAX_RETRIES,
                            exc,
                            delay,
                        )
                        await asyncio.sleep(delay)
        logger.error("AI call failed across all models: %s", last_error)
        raise AIServiceError from last_error


def get_ai_provider() -> AIProvider:
    settings = get_settings()
    if not settings.GEMINI_API_KEY:
        raise AIServiceError("GEMINI_API_KEY is not configured")
    return GeminiProvider(
        api_key=settings.GEMINI_API_KEY,
        model=settings.GEMINI_MODELS or [settings.GEMINI_MODEL],
    )
