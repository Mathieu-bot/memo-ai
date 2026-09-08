from typing import Any

from app.services.ai.base import AIProvider

FLASHCARD_SYSTEM_PROMPT = (
    "You are an expert study assistant specializing in active recall. "
    "You always respond with valid JSON only, with no markdown and no extra text."
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


class FlashcardService:
    def __init__(self, provider: AIProvider):
        self.provider = provider

    async def generate(self, content: str, num_cards: int = 10) -> list[dict[str, str]]:
        prompt = FLASHCARD_PROMPT_TEMPLATE.format(content=content, num_cards=num_cards)
        result: dict[str, Any] = await self.provider.generate_structured_json(
            prompt, system_prompt=FLASHCARD_SYSTEM_PROMPT
        )
        return result.get("flashcards", [])
