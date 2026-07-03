"""The answer capability with the honesty verdict FUSED in. Day-1 returns a stub."""

from app.agent.schemas import AnswerResult, GroundedAnswer
from app.retrieval.service import retrieve


async def answer(tenant_id: str, query: str) -> AnswerResult:
    # Day-1 stub: grounds against the (stubbed) retrieval and always returns the
    # verdict fused with the answer; there is no path that yields an answer without
    # one. Real grounding and the honest-refusal decision land on Day 6.
    sources = await retrieve(tenant_id, query)
    text = "(stub) grounded answer; real grounding and refusal land on Day 6."
    return AnswerResult(
        answer=text, verdict=GroundedAnswer(answer=text, sources=sources)
    )
