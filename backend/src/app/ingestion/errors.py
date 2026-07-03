"""Ingestion domain errors. A poison document is an EXPECTED outcome (the DLQ)."""

from app.core.errors import IngestionError


class PoisonDocumentError(IngestionError):
    """A document could not be parsed and must go to the DLQ, not crash the worker.

    The `reason` is a short, safe, human-readable classification (for example
    "encrypted", "malformed: ...", "extraction timeout", "extractor exited -11").
    It never carries raw file content or a stack trace.
    """

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)
