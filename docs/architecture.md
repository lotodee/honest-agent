# Architecture

## Overview

Honest Agent is one Python service (FastAPI + PydanticAI) that does three jobs:
ingests an owner's content, answers visitor questions grounded only in that
owner's content, and refuses honestly when it cannot ground an answer. The
reliability and evaluation layer is the product, not an add-on.

The service is domain-first. Each domain owns its router, schemas, service, and
exceptions; `core/` holds the cross-cutting wiring every domain depends on.

| Domain | Responsibility |
| --- | --- |
| `tenants` | Tenant records and the owner-facing scoping surface. |
| `ingestion` | Upload, queue, idempotent upsert, per-document status, poison-PDF DLQ. |
| `agent` | The PydanticAI agent: typed deps, grounded answer or honest refusal verdict. |
| `retrieval` | Tenant-scoped hybrid search over Weaviate. |
| `guardrails` | Prompt-injection pre-screen, faithfulness, the refusal decision. |
| `eval` | DeepEval golden set, the deterministic DAG gate, the online scorer. |
| `mcp` | The remote Streamable-HTTP MCP server: Origin-validated, bearer-token, scoped. |
| `core` | Settings, logging, observability, db seam, error contract, `get_current_tenant`. |

## The spine (protected on every change)

- **Tenant isolation**: tenant A cannot read or write tenant B, in both Postgres (RLS forced) and Weaviate (shard boundary). Proven by a test.
- **Poison-PDF survival**: a malformed PDF lands in the DLQ with a reason; the worker never crashes (parsing runs in a timeout-bounded subprocess).
- **Reproducible red-to-green eval gate**: a bad change turns the deterministic DAG gate red, the fix turns it green, repeatably.
- **Deployed**: the service is hosted, reachable, and shareable on request.

## Request and data flow

Diagram placeholder — to be added (ingestion path: presigned upload to object
storage, queue, content-hash dedupe, gated OCR / Gemini vision for image pages,
idempotent upsert into Weaviate per tenant; answer path: tenant-scoped hybrid
retrieval, agent run behind the model seam, typed verdict, one Logfire trace per run).

## Boundaries that matter

- API schemas are separate from internal and DB models; every route declares `response_model`.
- Tenant scoping lives in one shared dependency, `get_current_tenant`, injected into every tenant-touching router.
- The model is reached through one narrow provider interface in `agent/`; Gemini is the only live provider.
- Secrets are server-side (Backend-for-Frontend): the widget holds only a public widget key.

See `docs/adr/` for the decisions behind the toolchain and the layout.
