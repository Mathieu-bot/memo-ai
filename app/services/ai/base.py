from abc import ABC, abstractmethod
from typing import Any


class AIProvider(ABC):
    @abstractmethod
    async def generate_text(self, prompt: str, system_prompt: str = "") -> str: ...

    @abstractmethod
    async def generate_structured_json(
        self, prompt: str, system_prompt: str = ""
    ) -> dict[str, Any]: ...
