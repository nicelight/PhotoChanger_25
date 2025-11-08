"""Admin API routes for global settings."""

from fastapi import APIRouter, Depends, Request

from .settings_schemas import SettingsResponseModel, SettingsUpdateRequest
from .settings_service import SettingsService

router = APIRouter(prefix="/api/settings", tags=["settings"])


def get_settings_service(request: Request) -> SettingsService:
    try:
        return request.app.state.settings_service  # type: ignore[attr-defined]
    except AttributeError as exc:  # pragma: no cover - defensive path
        raise RuntimeError("SettingsService is not configured") from exc


@router.get("/", response_model=SettingsResponseModel)
def read_settings(service: SettingsService = Depends(get_settings_service)) -> SettingsResponseModel:
    snapshot = service.load()
    return SettingsResponseModel(**snapshot)


@router.put("/", response_model=SettingsResponseModel)
def update_settings(
    payload: SettingsUpdateRequest,
    service: SettingsService = Depends(get_settings_service),
) -> SettingsResponseModel:
    snapshot = service.update(payload.model_dump(exclude_none=True), actor="admin-ui")
    return SettingsResponseModel(**snapshot)
