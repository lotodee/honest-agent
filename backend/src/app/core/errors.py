"""The AppError hierarchy and the RFC 9457 problem-details handler."""

from fastapi import FastAPI, Request, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

_PROBLEM_BASE = "https://github.com/lotodee/honest-agent/problems"


class AppError(Exception):
    """Base for every error the service raises and maps to a problem response."""

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    title: str = "Internal Server Error"
    problem_type: str = "about:blank"

    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(detail)


class TenantAccessError(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    title = "Tenant Access Denied"
    problem_type = f"{_PROBLEM_BASE}/tenant-access"


class NotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    title = "Resource Not Found"
    problem_type = f"{_PROBLEM_BASE}/not-found"


class IngestionError(AppError):
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    title = "Ingestion Failed"
    problem_type = f"{_PROBLEM_BASE}/ingestion"


class GuardrailRefusal(AppError):  # noqa: N818  spec-mandated name; a refusal is a modeled outcome, not an "...Error"
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    title = "Guardrail Refusal"
    problem_type = f"{_PROBLEM_BASE}/guardrail-refusal"


class ProblemDetail(BaseModel):
    """The single RFC 9457 error envelope every client parses."""

    type: str
    title: str
    status: int
    detail: str
    instance: str


def _to_problem_response(request: Request, error: AppError) -> JSONResponse:
    problem = ProblemDetail(
        type=error.problem_type,
        title=error.title,
        status=error.status_code,
        detail=error.detail,
        instance=request.url.path,
    )
    return JSONResponse(
        status_code=error.status_code,
        content=problem.model_dump(),
        media_type="application/problem+json",
    )


def register_error_handlers(app: FastAPI) -> None:
    async def handle_app_error(request: Request, exc: Exception) -> Response:
        # Starlette types every handler as (Request, Exception); this one is only
        # registered for AppError, so the narrow always holds. The fallback
        # re-raises so an unexpected type reaches the default 500 handler intact.
        if isinstance(exc, AppError):
            return _to_problem_response(request, exc)
        raise exc

    app.add_exception_handler(AppError, handle_app_error)
