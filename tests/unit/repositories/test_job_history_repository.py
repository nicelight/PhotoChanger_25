from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.app.db.db_init import init_db
from src.app.db.db_models import JobHistoryModel
from src.app.repositories.job_history_repository import JobHistoryRepository


def test_create_pending_records_job() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    init_db(engine, session_factory)

    repo = JobHistoryRepository(session_factory)
    now = datetime.utcnow()
    repo.create_pending(
        job_id="job123",
        slot_id="slot-001",
        started_at=now,
        sync_deadline=now + timedelta(seconds=48),
        source="ui_test",
    )

    with session_factory() as session:
        row = session.get(JobHistoryModel, "job123")
        assert row is not None
        assert row.status == "pending"
        assert row.slot_id == "slot-001"
        assert row.source == "ui_test"
