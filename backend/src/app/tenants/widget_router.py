"""The visitor query endpoint. The gate middleware has already resolved the tenant."""

from fastapi import APIRouter, Request

from app.agent.adapters import answer_in_process
from app.agent.schemas import AnswerResult
from app.core.errors import AuthenticationError
from app.tenants.contexts import VisitorRequestContext

router = APIRouter(prefix="/widget", tags=["widget"])


@router.post("/answer", response_model=AnswerResult)
async def widget_answer(request: Request) -> AnswerResult:
    # The gate middleware put the sanitized, tenant-scoped context on request.state.
    # If it is absent the gate did not run, so fail closed rather than serve unscoped.
    context = getattr(request.state, "visitor_context", None)
    if not isinstance(context, VisitorRequestContext):
        raise AuthenticationError("visitor gate did not run")
    return await answer_in_process(context)
