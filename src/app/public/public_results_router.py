"""Public endpoint for result downloads."""

from fastapi import APIRouter

from ..media.public_result_service import PublicResultService


def build_public_results_router(service: PublicResultService) -> APIRouter:
    router = APIRouter(prefix="/public/results", tags=["public-results"])

    @router.get("/{job_id}")
    def get_result(job_id: str):
        return service.open_result(job_id)

    return router
