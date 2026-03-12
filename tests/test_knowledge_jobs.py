from __future__ import annotations

from sqlalchemy import select

from app.db.models import Project, ProjectSyncJob
from app.services.knowledge_jobs import create_sync_job, run_sync_job


def test_run_sync_job_missing_integration(session_factory) -> None:
    db = session_factory()
    project = Project(name="GridBox HeadEnd", slug="gridbox-headend", ownership_type="company")
    db.add(project)
    db.commit()
    db.refresh(project)

    job = create_sync_job(db, project=project, job_type="github_scan", requested_by="tester")
    run_sync_job(db, job=job, project=project)

    refreshed = db.scalar(select(ProjectSyncJob).where(ProjectSyncJob.id == job.id))
    assert refreshed is not None
    assert refreshed.status == "failed"
    assert "GitHub" in (refreshed.result_summary or "")
