"""Admin-only controls for public gallery sharing."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from ..auth.auth_dependencies import require_admin_user
from .public_gallery_service import GalleryShareState, utcnow


def build_public_gallery_admin_router(share_state: GalleryShareState) -> APIRouter:
    router = APIRouter(
        prefix="/api/gallery",
        tags=["gallery"],
        dependencies=[Depends(require_admin_user)],
    )

    @router.post("/share", status_code=status.HTTP_200_OK)
    def enable_public_share(minutes: int = 15) -> dict[str, str]:
        expires_at = share_state.enable(minutes=minutes)
        return {
            "status": "enabled",
            "share_until": expires_at.isoformat(),
            "requested_at": utcnow().isoformat(),
        }

    return router
