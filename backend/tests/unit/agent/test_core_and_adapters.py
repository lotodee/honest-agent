"""One core, two thin adapters, the verdict always fused into the answer."""

import inspect

from app.agent.adapters import answer_for_external_caller, answer_in_process
from app.agent.schemas import AnswerResult, GroundedAnswer
from app.agent.service import answer
from app.tenants.contexts import ExternalCallerContext, VisitorRequestContext


async def test_answer_fuses_the_verdict() -> None:
    result = await answer("tenant-a", "how do I reset my password?")
    assert isinstance(result, AnswerResult)
    assert result.answer
    # The verdict is present and structured, never optional free text.
    assert result.verdict.kind in {"grounded", "refusal"}


async def test_in_process_adapter_calls_the_core() -> None:
    context = VisitorRequestContext(tenant_id="tenant-a", query="hi")
    result = await answer_in_process(context)
    assert isinstance(result, AnswerResult)
    assert isinstance(result.verdict, GroundedAnswer)


async def test_external_caller_adapter_calls_the_same_core() -> None:
    context = ExternalCallerContext(tenant_id="tenant-a")
    result = await answer_for_external_caller(context, "hi")
    assert isinstance(result, AnswerResult)
    assert result.verdict.kind == "grounded"


async def test_both_adapters_return_the_same_shape() -> None:
    in_process = await answer_in_process(VisitorRequestContext("tenant-a", "q"))
    external = await answer_for_external_caller(ExternalCallerContext("tenant-a"), "q")
    assert type(in_process) is type(external) is AnswerResult


def test_external_caller_adapter_never_accepts_a_token() -> None:
    # No-passthrough at the signature level: the MCP token cannot flow to the core
    # because the adapter has no parameter to carry it.
    params = set(inspect.signature(answer_for_external_caller).parameters)
    assert params == {"context", "query"}
    assert not {"token", "authorization", "bearer", "credential"} & params
