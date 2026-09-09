from app.services.ai.base import AIProvider

SUMMARY_SYSTEM_PROMPT = (
    "You are an expert study assistant. Provide a clear, concise summary "
    "of the given educational content in plain text. Base the summary "
    "ONLY on the provided content; do not add outside knowledge. "
    "If the content is empty or insufficient, say so."
)

SUMMARY_PROMPT_TEMPLATE = (
    "Summarize the following educational content.\n"
    "Keep the summary structured, highlighting the most important "
    "concepts and key takeaways.\n"
    "Use plain text with short paragraphs.\n\n"
    "Content:\n{content}"
)


class SummaryService:
    def __init__(self, provider: AIProvider):
        self.provider = provider

    async def summarize(self, content: str) -> str:
        prompt = SUMMARY_PROMPT_TEMPLATE.format(content=content)
        return await self.provider.generate_text(
            prompt, system_prompt=SUMMARY_SYSTEM_PROMPT
        )
