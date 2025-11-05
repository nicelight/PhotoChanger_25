"""Public media endpoints (provider access)."""

from fastapi import APIRouter

from ..media.public_media_service import PublicMediaService


def build_public_media_router(service: PublicMediaService) -> APIRouter:
    router = APIRouter(prefix="/public/provider-media", tags=["public-media"])

    @router.get("/{media_id}")
    def get_media(media_id: str):
        return service.open_media(media_id)

    return router
