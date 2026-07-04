# 7. Vertex model, location, and embedding-dimension config

Date: 2026-07-04

## Status

Accepted

Corrects ARCHITECTURE.md Delta 4, whose recommended `gemini-3-flash` does not exist.

## Context

A local Vertex pre-flight (`scripts/probe_vertex.py`, credential-gated, run against our
real GCP project) tried the intended `gemini-3-flash` and got a 404 in every candidate
location. `models.list()`
showed the real ids: the Gemini-3 flash family (`gemini-3.5-flash`,
`gemini-3-flash-preview`, `gemini-3.1-flash-lite`) is served **only at location
`global`**; the regional locations tried (us-central1, us-east4, us-east5,
europe-west4) serve the 2.5 family (`gemini-2.5-flash`). `gemini-embedding-001` works
in every location but returns **3072** dimensions natively, while the durable
`chunks.embedding` column is `vector(768)`. A follow-up probe confirmed
`output_dimensionality=768` returns a 768-vector but **un-normalized** (L2-norm ≈ 0.59,
versus ≈ 1.0 at the native 3072), because MRL truncation drops magnitude — so a 768
embedding MUST be re-normalized before use.

## Decision

- **Generation / vision:** `gemini-3.5-flash` (the real current flash), at location
  **`global`**.
- **Embeddings:** `gemini-embedding-001`, with the embed call (wired Day 4) requesting
  `output_dimensionality=768` and **L2-normalizing** the vector so it fits
  `chunks.embedding vector(768)`.
- **Regional fallback (documented only, not wired):** `us-central1` +
  `gemini-2.5-flash`, for when global routing or data residency requires a region.
- **Code-defaulted but env-overridable** in `core/settings.py`: `generation_model`
  (`GENERATION_MODEL`), `embedding_model` (`EMBEDDING_MODEL`), and `gcp_location`
  (`GCP_LOCATION`). A field is overridden by its uppercase env var automatically, so
  switching a model is one env var. Model names live ONLY in Settings.
- **The embedding dimension is NOT env-overridable.** It is a fixed module constant,
  `core/settings.py:EMBEDDING_DIM = 768`, because it is coupled 1:1 to the
  `chunks.embedding vector(N)` column and must never drift at runtime. A schema-match
  unit test parses `0003_chunks.sql` and asserts the column's `vector(N)` equals the
  constant, so any drift fails CI.

## Consequences

- The invalid `gemini-3-flash` default is fixed; a wrong model id is now a config
  value, not a surprise 404 on the first real call.
- `generation_model` and `gcp_location` are free to flip via env. `embedding_dim` is a
  pinned constant guarded by the schema-match test; changing it is a coordinated
  code + migration + re-embed change, never a runtime env flip.
- Day 4's embed call MUST pass `output_dimensionality=768` and normalize; a raw
  `gemini-embedding-001` call returns 3072 and would fail to insert into `vector(768)`.
- Supersedes ARCHITECTURE.md Delta 4's `gemini-3-flash` recommendation.

## Rechecking this decision

- `scripts/probe_vertex.py` reproduces the pre-flight on demand: credential-gated
  (reads `GOOGLE_CREDENTIALS_B64` / `GCP_PROJECT` from the env, never runs in CI, never
  prints the credential), it lists model availability per location and confirms
  `gemini-3.5-flash` at `global` and the `gemini-embedding-001` dimensions. Anyone can
  re-verify the claims above with it.
- Day 4's credential-gated vision integration test is the AUTOMATED recheck of the live
  path: a real image page must return a real, non-placeholder description.
