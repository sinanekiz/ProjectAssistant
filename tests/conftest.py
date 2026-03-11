from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import get_settings
from app.db.base import Base
from app.db.session import get_db
from app.main import app


@pytest.fixture(autouse=True)
def clear_settings_cache() -> None:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def isolate_runtime_files(tmp_path: Path, monkeypatch) -> None:
    from app.services import activity_store, setup_manager

    monkeypatch.setattr(setup_manager, "ENV_FILE_PATH", tmp_path / ".env")
    monkeypatch.setattr(activity_store, "RUNTIME_DIR", tmp_path / "runtime")
    monkeypatch.setattr(activity_store, "ACTIVITY_FILE_PATH", tmp_path / "runtime" / "activity.jsonl")
    monkeypatch.setattr(activity_store, "QUESTIONS_FILE_PATH", tmp_path / "runtime" / "questions.jsonl")
    yield


@pytest.fixture()
def session_factory() -> sessionmaker[Session]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


@pytest.fixture()
def client(session_factory: sessionmaker[Session]) -> TestClient:
    def override_get_db() -> Session:
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
