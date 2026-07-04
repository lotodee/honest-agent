"""Vertex pre-flight probe (ADR-0007). Credential-gated dev tool, NEVER run in CI.

Rechecks the model/location decision on demand. Provide GOOGLE_CREDENTIALS_B64 and
GCP_PROJECT in the environment (or in backend/.env); the probe lists model availability
per location and confirms gemini-3.5-flash at `global` and the gemini-embedding-001
dimensions. It never prints the credential, and it fails soft (exit 0) when no
credential is present, so it can never break CI or a scripted run.

    uv run python scripts/probe_vertex.py
"""

import base64
import json
import math
import os
import pathlib

_BACKEND_ENV = pathlib.Path(__file__).resolve().parents[1] / ".env"
GEN_MODEL = "gemini-3.5-flash"
EMB_MODEL = "gemini-embedding-001"
EMB_DIM = 768
LOCATIONS = ("global", "us-central1", "us-east4", "us-east5", "europe-west4")
_SCOPES = ("https://www.googleapis.com/auth/cloud-platform",)


def _read(key: str) -> str | None:
    """The value from the environment, else from backend/.env. Never printed."""
    value = os.environ.get(key)
    if value:
        return value
    if _BACKEND_ENV.is_file():
        for line in _BACKEND_ENV.read_text(encoding="utf-8").splitlines():
            if line.startswith(f"{key}="):
                return line.split("=", 1)[1].strip()
    return None


def _first_line(exc: Exception) -> str:
    text = str(exc)
    return text.splitlines()[0][:60] if text else type(exc).__name__


def main() -> int:
    b64 = _read("GOOGLE_CREDENTIALS_B64")
    project = _read("GCP_PROJECT")
    if not b64 or not project:
        print(
            "no Vertex credential; set GOOGLE_CREDENTIALS_B64 and GCP_PROJECT to run."
        )
        return 0

    from google import genai
    from google.genai import types
    from google.oauth2 import service_account

    creds = service_account.Credentials.from_service_account_info(
        json.loads(base64.b64decode(b64)), scopes=list(_SCOPES)
    )
    print(
        f"credential decoded in memory (not shown). SA: {creds.service_account_email}"
    )

    rows: list[tuple[str, str, str]] = []
    for loc in LOCATIONS:
        try:
            client = genai.Client(
                vertexai=True, project=project, location=loc, credentials=creds
            )
        except Exception as exc:  # a probe records failures, it does not crash
            rows.append((loc, f"client err: {_first_line(exc)}", "-"))
            continue

        try:
            client.models.generate_content(model=GEN_MODEL, contents="ping")
            gen = "OK"
        except Exception as exc:
            gen = f"ERR {_first_line(exc)}"

        try:
            result = client.models.embed_content(
                model=EMB_MODEL,
                contents="ping",
                config=types.EmbedContentConfig(output_dimensionality=EMB_DIM),
            )
            values = result.embeddings[0].values
            norm = math.sqrt(sum(x * x for x in values))
            emb = f"OK dim={len(values)} norm={norm:.2f}"
        except Exception as exc:
            emb = f"ERR {_first_line(exc)}"

        rows.append((loc, gen, emb))
        if gen.startswith("ERR") or emb.startswith("ERR"):
            ids = [m.name.split("/")[-1] for m in client.models.list()]
            print(f"[{loc}] {len(ids)} models: {', '.join(ids)}")

    print(f"\n{'location':<14} {f'gen({GEN_MODEL})':<26} embed({EMB_MODEL}@{EMB_DIM})")
    for loc, gen, emb in rows:
        print(f"{loc:<14} {gen:<26} {emb}")
    both = next((loc for loc, g, e in rows if g == "OK" and e.startswith("OK")), None)
    print(f"\nfirst location where both work: {both or 'NONE'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
