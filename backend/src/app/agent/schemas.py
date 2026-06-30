"""The agent's typed output: a grounded answer or an honest refusal, never free text."""

from typing import Annotated, Literal

from pydantic import BaseModel, Field


class Source(BaseModel):
    document_id: str
    chunk_id: str
    score: float


class GroundedAnswer(BaseModel):
    kind: Literal["grounded"] = "grounded"
    answer: str
    sources: list[Source]


class HonestRefusal(BaseModel):
    kind: Literal["refusal"] = "refusal"
    reason: str


# The agent's PydanticAI output_type. A refusal is a modeled outcome, not an
# exception, so the discriminator decides which branch the caller handles.
Verdict = Annotated[GroundedAnswer | HonestRefusal, Field(discriminator="kind")]


class AnswerResult(BaseModel):
    """The fused result every `answer` call returns: the text AND its verdict.

    `answer` is the rendered text a client displays; `verdict` is the structured
    honesty decision (grounded with sources, or a refusal with a reason) a client
    enforces against. The verdict is never optional, because honesty is the product.
    """

    answer: str
    verdict: Verdict
