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


class AuthenticationError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    title = "Authentication Failed"
    problem_type = f"{_PROBLEM_BASE}/authentication"


class TenantAccessError(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    title = "Tenant Access Denied"
    problem_type = f"{_PROBLEM_BASE}/tenant-access"


class PayloadTooLargeError(AppError):
    status_code = status.HTTP_413_CONTENT_TOO_LARGE
    title = "Payload Too Large"
    problem_type = f"{_PROBLEM_BASE}/payload-too-large"


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


def problem_response(
    *,
    status_code: int,
    title: str,
    problem_type: str,
    detail: str,
    instance: str,
) -> JSONResponse:
    """Build one RFC 9457 problem-details response. Used by handlers and middleware."""
    problem = ProblemDetail(
        type=problem_type,
        title=title,
        status=status_code,
        detail=detail,
        instance=instance,
    )
    return JSONResponse(
        status_code=status_code,
        content=problem.model_dump(),
        media_type="application/problem+json",
    )


def app_error_response(error: AppError, *, instance: str) -> JSONResponse:
    return problem_response(
        status_code=error.status_code,
        title=error.title,
        problem_type=error.problem_type,
        detail=error.detail,
        instance=instance,
    )


def register_error_handlers(app: FastAPI) -> None:
    async def handle_app_error(request: Request, exc: Exception) -> Response:
        # Starlette types every handler as (Request, Exception); this one is only
        # registered for AppError, so the narrow always holds. The fallback
        # re-raises so an unexpected type reaches the default 500 handler intact.
        if isinstance(exc, AppError):
            return app_error_response(exc, instance=request.url.path)
        raise exc

    app.add_exception_handler(AppError, handle_app_error)
