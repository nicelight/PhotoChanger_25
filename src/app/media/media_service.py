"""Result storage handling."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from ..config import MediaPaths


@dataclass(slots=True)
class ResultStore:
    """Manage storing processed media results on disk."""

    paths: MediaPaths

    def result_dir(self, slot_id: str, job_id: str) -> Path:
        return self.paths.results / slot_id / job_id

    def ensure_structure(self, slot_id: str, job_id: str) -> Path:
        directory = self.result_dir(slot_id, job_id)
        directory.mkdir(parents=True, exist_ok=True)
        return directory

    def save_payload(self, slot_id: str, job_id: str, data: bytes, suffix: str) -> Path:
        directory = self.ensure_structure(slot_id, job_id)
        sanitized = suffix.lstrip(".") or "bin"
        path = directory / f"payload.{sanitized}"
        path.write_bytes(data)
        return path

    def remove_result_dir(self, slot_id: str, job_id: str) -> None:
        directory = self.result_dir(slot_id, job_id)
        if directory.exists():
            shutil.rmtree(directory, ignore_errors=True)
