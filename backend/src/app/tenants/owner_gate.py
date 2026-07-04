"""Owner-door body-size cap: in-app FastAPI middleware on the owner route surface.

Defense-in-depth only. It rejects on the DECLARED Content-Length header before the
body is read. Unlike the visitor gate (tenants/gate.py), it does NOT then measure the
actual bytes received: buffering an unread body here purely to size it would
reintroduce the very memory-DoS the header check avoids, and owner routes read no
body today. LIMITATION: a missing or understated Content-Length (e.g. a chunked body)
is not caught here. A future owner route that PARSES a body must enforce the
real-bytes cap on what it actually read (as the visitor gate does) and must not rely
on this middleware alone. This does not address the JWKS-refetch amplification (that
is header-driven and handled in owner_auth's resolver).
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
