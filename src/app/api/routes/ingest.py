"""External ingest router stub for DSLR Remote Pro payloads."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path, Request, UploadFile, status
from fastapi.responses import JSONResponse

from ..schemas import IngestRequest, SlotIdentifier
from .responses import endpoint_not_implemented

router = APIRouter(tags=["Ingest"])


async def _parse_ingest_payload(request: Request) -> IngestRequest:
    """Transform a multipart ingest submission into the contract schema."""

    form = await request.form()
    data: dict[str, Any] = {}

    for key, value in form.multi_items():
        if isinstance(value, UploadFile):
            data[key] = await value.read()
        else:
            data[key] = value

    return IngestRequest.model_validate(data)


@router.post(
    "/ingest/{slotId}",
    status_code=status.HTTP_200_OK,
)
async def ingest_slot(
    slot_id: Annotated[SlotIdentifier, Path(alias="slotId", description="Статический идентификатор ingest-слота")],
    payload: Annotated[IngestRequest, Depends(_parse_ingest_payload)],
) -> JSONResponse:
    """Принять ingest-запрос от DSLR Remote Pro."""

    _ = (slot_id, payload)
    return endpoint_not_implemented("ingestSlot")


__all__ = ["router", "ingest_slot"]
