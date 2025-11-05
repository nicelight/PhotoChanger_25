"""Cron entry point for cleaning expired media results."""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from datetime import datetime

from src.app.config import load_config
from src.app.media.media_cleanup import cleanup_expired_results
from src.app.media.media_service import ResultStore
from src.app.media.temp_media_store import TempMediaStore
from src.app.repositories.media_object_repository import MediaObjectRepository


@dataclass(slots=True)
class CleanupSummary:
    results_removed: int
    temp_removed: int
    dry_run: bool


def perform_cleanup(*, dry_run: bool, reference_time: datetime | None = None) -> CleanupSummary:
    """Execute cleanup logic and return summary counters."""
    config = load_config()
    media_repo = MediaObjectRepository(config.session_factory)
    result_store = ResultStore(config.media_paths)
    temp_store = TempMediaStore(
        paths=config.media_paths,
        media_repo=media_repo,
        temp_ttl_seconds=config.temp_ttl_seconds,
    )

    now = reference_time or datetime.utcnow()

    if dry_run:
        expired_results = media_repo.list_expired_results(now)
        expired_temp = media_repo.list_expired_by_scope("provider", now)
        return CleanupSummary(results_removed=len(expired_results), temp_removed=len(expired_temp), dry_run=True)

    removed_results = cleanup_expired_results(media_repo, result_store, now)
    removed_temp = temp_store.cleanup_expired(now)
    return CleanupSummary(results_removed=removed_results, temp_removed=removed_temp, dry_run=False)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Cleanup expired media artifacts.")
    parser.add_argument("--dry-run", action="store_true", help="Only report counts without deleting files.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or [])
    try:
        summary = perform_cleanup(dry_run=args.dry_run)
    except Exception as exc:
        print(f"cleanup failed: {exc}", file=sys.stderr)
        return 2

    if summary.dry_run:
        print(
            f"cleanup dry-run, results_expired={summary.results_removed}, temp_expired={summary.temp_removed}",
            file=sys.stdout,
        )
    else:
        print(
            f"cleanup done, results_removed={summary.results_removed}, temp_removed={summary.temp_removed}",
            file=sys.stdout,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
