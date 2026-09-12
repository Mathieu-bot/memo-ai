import asyncio
import logging
from typing import Any

from app.services.ai.base import AIProvider

logger = logging.getLogger(__name__)

QUIZ_SYSTEM_PROMPT = (
    "You are an expert educational content creator. "
    "You always respond with valid JSON only, with no markdown and no extra text. "
    "Base every question ONLY on the provided content; do not use outside "
    "knowledge. If the content does not support a required number of questions, "
    "generate fewer questions instead of inventing facts."
)

QUIZ_PROMPT_TEMPLATE = (
    "Generate a quiz with {num_questions} questions about: {title}\n\n"
    "Course content: {description}\n\n"
    "Return EXACTLY this JSON structure:\n"
    "{{\n"
    '  "title": "Quiz: {title}",\n'
    '  "description": "Test your knowledge about {title}",\n'
    '  "questions": [\n'
    "    {{\n"
    '      "text": "Question text here",\n'
    '      "explanation": "Explanation of the correct answer",\n'
    '      "answers": [\n'
    '        {{"text": "Option A", "is_correct": true}},\n'
    '        {{"text": "Option B", "is_correct": false}},\n'
    '        {{"text": "Option C", "is_correct": false}},\n'
    '        {{"text": "Option D", "is_correct": false}}\n'
    "      ]\n"
    "    }}\n"
    "  ]\n"
    "}}\n\n"
    "Every question must have exactly 4 answers and only one correct "
    "answer. Do not include any other fields."
)

# The provider already retries transport errors; this handles the (rarer)
# case where the model answers with syntactically valid JSON that does not
# satisfy the expected structure.
STRUCTURE_ATTEMPTS = 3
STRUCTURE_RETRY_BASE_DELAY_SECONDS = 0.5


class QuizGenerator:
    def __init__(self, provider: AIProvider):
        self.provider = provider

    @staticmethod
    def _is_valid(data: Any) -> bool:
        if not isinstance(data, dict):
            return False
        questions = data.get("questions")
        return (
            bool(data.get("title")) and isinstance(questions, list) and bool(questions)
        )

    async def generate(
        self, title: str, description: str, num_questions: int = 5
    ) -> dict[str, Any]:
        prompt = QUIZ_PROMPT_TEMPLATE.format(
            title=title, description=description or "", num_questions=num_questions
        )
        result: dict[str, Any] = {}
        for attempt in range(STRUCTURE_ATTEMPTS):
            result = await self.provider.generate_structured_json(
                prompt, system_prompt=QUIZ_SYSTEM_PROMPT
            )
            if self._is_valid(result):
                return result
            if attempt < STRUCTURE_ATTEMPTS - 1:
                delay = STRUCTURE_RETRY_BASE_DELAY_SECONDS * (2**attempt)
                logger.warning(
                    "Invalid quiz structure retried (attempt %d/%d), waiting %.1fs",
                    attempt + 1,
                    STRUCTURE_ATTEMPTS,
                    delay,
                )
                await asyncio.sleep(delay)
        # Let the caller decide how to surface the last invalid response.
        return result
