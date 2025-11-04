"""Cron entry point for cleaning expired media results."""

from datetime import datetime

from src.app.config import load_config
from src.app.media.media_cleanup import cleanup_expired_results
from src.app.media.media_service import ResultStore
from src.app.media.temp_media_store import TempMediaStore
from src.app.repositories.media_object_repository import MediaObjectRepository


def main() -> None:
    config = load_config()
    media_repo = MediaObjectRepository(config.session_factory)
    result_store = ResultStore(config.media_paths)
    temp_store = TempMediaStore(
        paths=config.media_paths,
        media_repo=media_repo,
        temp_ttl_seconds=config.temp_ttl_seconds,
    )
    reference_time = datetime.utcnow()
    removed_results = cleanup_expired_results(media_repo, result_store, reference_time)
    removed_temp = temp_store.cleanup_expired(reference_time)
    print(f"cleanup done, results_removed={removed_results}, temp_removed={removed_temp}")


if __name__ == "__main__":
    main()
