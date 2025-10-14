"""External ingest router stub for DSLR Remote Pro payloads."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Path, status
from fastapi.responses import JSONResponse

from ..schemas import IngestRequest, SlotIdentifier
from .responses import endpoint_not_implemented

router = APIRouter(tags=["Ingest"])


@router.post(
    "/ingest/{slotId}",
    status_code=status.HTTP_200_OK,
)
async def ingest_slot(
    slot_id: Annotated[
        SlotIdentifier,
        Path(alias="slotId", description="Статический идентификатор ingest-слота"),
    ],
    payload: IngestRequest,
) -> JSONResponse:
    """Принять ingest-запрос от DSLR Remote Pro."""

    _ = (slot_id, payload)
    return endpoint_not_implemented("ingestSlot")


__all__ = ["router", "ingest_slot"]
