"""The narrow multi-provider seam. Gemini via Vertex AI is the only live model."""

from typing import Protocol


class ModelProvider(Protocol):
    """One interface over the generation backend.

    Gemini via Vertex AI is the live provider and the only one we ship; Vertex is
    used purely as the Gemini API, never for hosting. This interface stays narrow
    so a documented fallback provider can be added without touching agent logic.
    """

    model_name: str

    async def complete(self, *, system: str, prompt: str) -> str: ...

    async def embed(self, texts: list[str]) -> list[list[float]]: ...
