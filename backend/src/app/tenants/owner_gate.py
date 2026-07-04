"""Owner-door body-size cap: in-app FastAPI middleware on the owner route surface.

Defense-in-depth only. The owner routes read no body today, and it does NOT address
the JWKS-refetch amplification (that is header-driven and handled in owner_auth's
resolver). It mirrors the visitor gate's pre-parse content-length check.
"""

from fastapi import FastAPI, Request, Response
from starlette.middleware.base import RequestResponseEndpoint

from app.core.errors import PayloadTooLargeError, app_error_response

# The owner-door route surface today. Scoped deliberately: the ingestion upload path
# (/v1/ingestion, Days 3-4) carries large PDFs and must NOT inherit this small cap.
OWNER_PATH_PREFIX = "/v1/tenants"


def install_owner_body_cap(app: FastAPI, max_body_bytes: int) -> None:
    @app.middleware("http")
    async def owner_body_cap_middleware(
        request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if request.url.path.startswith(OWNER_PATH_PREFIX):
            declared = request.headers.get("content-length")
            if (
                declared is not None
                and declared.isdigit()
                and int(declared) > max_body_bytes
            ):
                return app_error_response(
                    PayloadTooLargeError("declared body exceeds the owner limit"),
                    instance=request.url.path,
                )
        return await call_next(request)
