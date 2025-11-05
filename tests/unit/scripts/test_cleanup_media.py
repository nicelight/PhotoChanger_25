from datetime import datetime
import importlib.util
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
MODULE_PATH = PROJECT_ROOT / "scripts" / "cleanup_media.py"
SPEC = importlib.util.spec_from_file_location("cleanup_media_module", MODULE_PATH)
cleanup_media = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules["cleanup_media_module"] = cleanup_media
SPEC.loader.exec_module(cleanup_media)


class DummyConfig:
    def __init__(self):
        self.session_factory = object()
        self.media_paths = object()
        self.temp_ttl_seconds = 123


class DummyRepo:
    def __init__(self, session_factory):
        assert session_factory is not None

    def list_expired_results(self, reference_time):
        assert isinstance(reference_time, datetime)
        return ["expired-result-1", "expired-result-2"]

    def list_expired_by_scope(self, scope, reference_time):
        assert scope == "provider"
        assert isinstance(reference_time, datetime)
        return ["expired-temp"]


class DummyResultStore:
    def __init__(self, media_paths):
        self.media_paths = media_paths


class DummyTempStore:
    def __init__(self, paths, media_repo, temp_ttl_seconds):
        self.paths = paths
        self.media_repo = media_repo
        self.temp_ttl_seconds = temp_ttl_seconds
        self.cleaned_at = None

    def cleanup_expired(self, reference_time):
        self.cleaned_at = reference_time
        return 3


def test_perform_cleanup_dry_run(monkeypatch):
    monkeypatch.setattr(cleanup_media, "load_config", lambda: DummyConfig())
    monkeypatch.setattr(cleanup_media, "MediaObjectRepository", DummyRepo)

    summary = cleanup_media.perform_cleanup(dry_run=True, reference_time=datetime.utcnow())

    assert summary.dry_run is True
    assert summary.results_removed == 2
    assert summary.temp_removed == 1


def test_perform_cleanup_executes_cleanup(monkeypatch):
    reference_time = datetime.utcnow()

    monkeypatch.setattr(cleanup_media, "load_config", lambda: DummyConfig())
    monkeypatch.setattr(cleanup_media, "MediaObjectRepository", DummyRepo)
    monkeypatch.setattr(cleanup_media, "ResultStore", DummyResultStore)
    monkeypatch.setattr(cleanup_media, "TempMediaStore", DummyTempStore)

    called = {}

    def fake_cleanup_expired(media_repo, result_store, ref_time):
        called["repo"] = media_repo
        called["store"] = result_store
        called["time"] = ref_time
        return 5

    monkeypatch.setattr(cleanup_media, "cleanup_expired_results", fake_cleanup_expired)

    summary = cleanup_media.perform_cleanup(dry_run=False, reference_time=reference_time)

    assert summary.dry_run is False
    assert summary.results_removed == 5
    assert summary.temp_removed == 3
    assert called["time"] == reference_time


def test_main_handles_errors(monkeypatch, capsys):
    monkeypatch.setattr(cleanup_media, "perform_cleanup", lambda **kwargs: (_ for _ in ()).throw(RuntimeError("boom")))

    exit_code = cleanup_media.main([])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "cleanup failed" in captured.err
    assert "boom" in captured.err
