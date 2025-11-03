"""Cron entry point for cleaning expired media results."""

from datetime import datetime

from src.app.config import load_config
from src.app.media.media_cleanup import cleanup_expired_results
from src.app.media.media_service import ResultStore
from src.app.repositories.media_object_repository import MediaObjectRepository


def main() -> None:
    config = load_config()
    media_repo = MediaObjectRepository(config.session_factory)
    result_store = ResultStore(config.media_paths)
    removed = cleanup_expired_results(media_repo, result_store, datetime.utcnow())
    print(f"cleanup done, removed={removed}")


if __name__ == "__main__":
    main()
