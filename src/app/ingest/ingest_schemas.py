"""Pydantic schemas for ingest responses."""

from pydantic import BaseModel


class IngestErrorSchema(BaseModel):
    status: str
    failure_reason: str
    details: str | None = None
