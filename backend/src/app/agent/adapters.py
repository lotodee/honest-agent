"""Two thin adapters over the one core `answer`. No business logic lives here.

The widget gate uses the in-process adapter; the MCP tool uses the external-caller
adapter. Both translate their edge into the same core call and back, so there is
one core and no duplicated logic.
"""

from app.agent.schemas import AnswerResult
from app.agent.service import answer
from app.tenants.contexts import ExternalCallerContext, VisitorRequestContext


async def answer_in_process(context: VisitorRequestContext) -> AnswerResult:
    # The widget gate calls this directly in-process: no network hop, never via MCP.
    return await answer(context.tenant_id, context.query)


async def answer_for_external_caller(
    context: ExternalCallerContext, query: str
) -> AnswerResult:
    # The MCP tool calls this. The inbound MCP token is deliberately NOT a parameter
    # and never reaches the core: only the tenant (already resolved from the token)
    # and the query flow in. This signature is the no-token-passthrough boundary.
    return await answer(context.tenant_id, query)
