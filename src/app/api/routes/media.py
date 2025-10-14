"""Media management router stubs covering temporary and template uploads.

The endpoints mirror admin contracts for registering ingest payloads, template
media and purging resources without performing any business logic in phase 2,
keeping parity with ``spec/contracts/openapi.yaml``.
"""

from __future__ import annotations

from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Query, status
from fastapi.responses import JSONResponse

from ..schemas import (
    MediaObject,
    MediaRegisterRequest,
    SlotIdentifier,
    TemplateMediaObject,
    TemplateMediaRegisterRequest,
)
from .dependencies import require_bearer_authentication
from .responses import authentication_not_configured, endpoint_not_implemented

router = APIRouter(prefix="/api", tags=["Media"])


@router.post(
    "/media/register",
    response_model=MediaObject,
    status_code=status.HTTP_201_CREATED,
)
async def register_media(
    authenticated: Annotated[bool, Depends(require_bearer_authentication)],
    payload: MediaRegisterRequest,
) -> JSONResponse:
    """Зарегистрировать временное медиа и получить публичную ссылку."""

    _ = payload
    if not authenticated:
        return authentication_not_configured()
    return endpoint_not_implemented("registerMedia")


@router.post(
    "/template-media/register",
    response_model=TemplateMediaObject,
    status_code=status.HTTP_201_CREATED,
)
async def register_template_media(
    authenticated: Annotated[bool, Depends(require_bearer_authentication)],
    payload: TemplateMediaRegisterRequest,
) -> JSONResponse:
    """Загрузить шаблон и привязать его к слоту."""

    _ = payload
    if not authenticated:
        return authentication_not_configured()
    return endpoint_not_implemented("registerTemplateMedia")


@router.delete(
    "/template-media/{media_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_template_media(
    authenticated: Annotated[bool, Depends(require_bearer_authentication)],
    media_id: Annotated[UUID, Path(description="Идентификатор шаблонного медиа")],
    slot_id: Annotated[
        SlotIdentifier,
        Query(description="Слот, из которого удаляется привязка"),
    ],
    setting_key: Annotated[
        str, Query(description="Ключ настройки, который ссылался на шаблон")
    ],
    force: Annotated[
        Optional[bool],
        Query(description="Удалить файл даже при нескольких привязках"),
    ] = None,
) -> JSONResponse:
    """Удалить шаблонное медиа и отвязать от слота."""

    _ = (media_id, slot_id, setting_key, force)
    if not authenticated:
        return authentication_not_configured()
    return endpoint_not_implemented("deleteTemplateMedia")


__all__ = [
    "router",
    "register_media",
    "register_template_media",
    "delete_template_media",
]
