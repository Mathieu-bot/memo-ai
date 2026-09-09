import asyncio
import logging
from typing import Any

from app.services.ai.base import AIProvider

logger = logging.getLogger(__name__)

FLASHCARD_SYSTEM_PROMPT = (
    "You are an expert study assistant specializing in active recall. "
    "You always respond with valid JSON only, with no markdown and no extra text. "
    "Base every flashcard ONLY on the provided content; do not use outside "
    "knowledge. If the content does not support the requested number of cards, "
    "generate fewer cards instead of inventing facts."
)

FLASHCARD_PROMPT_TEMPLATE = (
    "Generate {num_cards} flashcards from the following educational "
    "content to help a student memorize key concepts.\n\n"
    "Content:\n{content}\n\n"
    "Return EXACTLY this JSON structure:\n"
    "{{\n"
    '  "flashcards": [\n'
    "    {{\n"
    '      "front": "Question or prompt on the front of the card",\n'
    '      "back": "Answer or explanation on the back of the card"\n'
    "    }}\n"
    "  ]\n"
    "}}\n\n"
    "Do not include any other fields."
)

# The provider already retries transport errors; this handles the (rarer)
# case where the model answers with syntactically valid JSON that does not
# contain usable cards.
STRUCTURE_ATTEMPTS = 3
STRUCTURE_RETRY_BASE_DELAY_SECONDS = 0.5


class FlashcardService:
    def __init__(self, provider: AIProvider):
        self.provider = provider

    @staticmethod
    def _is_valid(data: dict[str, Any]) -> bool:
        cards = data.get("flashcards")
        return isinstance(cards, list) and bool(cards)

    async def generate(self, content: str, num_cards: int = 10) -> list[dict[str, str]]:
        prompt = FLASHCARD_PROMPT_TEMPLATE.format(content=content, num_cards=num_cards)
        for attempt in range(STRUCTURE_ATTEMPTS):
            result: dict[str, Any] = await self.provider.generate_structured_json(
                prompt, system_prompt=FLASHCARD_SYSTEM_PROMPT
            )
            if self._is_valid(result):
                return result["flashcards"]
            if attempt < STRUCTURE_ATTEMPTS - 1:
                delay = STRUCTURE_RETRY_BASE_DELAY_SECONDS * (2**attempt)
                logger.warning(
                    "Empty flashcards result retried (attempt %d/%d), waiting %.1fs",
                    attempt + 1,
                    STRUCTURE_ATTEMPTS,
                    delay,
                )
                await asyncio.sleep(delay)
        # The caller treats an empty result as "nothing generated" rather
        # than a hard error, so keep that contract after exhausting retries.
        return []
