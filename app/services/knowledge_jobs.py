from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.db.models import Project, ProjectSyncJob
from app.logging import get_logger
from app.services.github_context import refresh_github_context
from app.services.gmail_context import refresh_gmail_context

logger = get_logger(__name__)


@dataclass(slots=True)
class JobCreateResult:
    job: ProjectSyncJob
    created: bool


def create_sync_job(
    db: Session,
    *,
    project: Project,
    job_type: str,
    requested_by: str | None = None,
    payload: dict | None = None,
) -> ProjectSyncJob:
    job = ProjectSyncJob(
        project_id=project.id,
        job_type=job_type.strip(),
        status="queued",
        requested_by=requested_by,
        payload=payload or {},
        started_at=None,
        finished_at=None,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    logger.info("project_sync_job_created", extra={"project_id": project.id, "job_id": job.id, "job_type": job.job_type})
    return job


def list_sync_jobs(db: Session, *, project: Project, limit: int = 50) -> list[ProjectSyncJob]:
    return list(
        db.scalars(
            select(ProjectSyncJob)
            .where(ProjectSyncJob.project_id == project.id)
            .order_by(desc(ProjectSyncJob.created_at))
            .limit(limit)
        )
    )


def run_sync_job(db: Session, *, job: ProjectSyncJob, project: Project) -> ProjectSyncJob:
    job.status = "running"
    job.started_at = datetime.utcnow()
    db.commit()
    db.refresh(job)

    try:
        summary, status = _execute_job(db=db, job=job, project=project)
        job.status = status
        job.result_summary = summary
    except Exception as exc:
        job.status = "failed"
        job.result_summary = str(exc)
        logger.warning("project_sync_job_failed", extra={"job_id": job.id, "job_type": job.job_type, "error": str(exc)})

    job.finished_at = datetime.utcnow()
    db.commit()
    db.refresh(job)
    return job


def _execute_job(db: Session, *, job: ProjectSyncJob, project: Project) -> tuple[str, str]:
    job_type = job.job_type
    if job_type == "github_scan":
        result = refresh_github_context(db, project=project)
        if "bulunamadi" in result.summary or "eksik" in result.summary:
            raise RuntimeError(result.summary)
        return result.summary, "success"
    if job_type == "gmail_style":
        result = refresh_gmail_context(db, project=project)
        if "bulunamadi" in result.summary or "eksik" in result.summary:
            raise RuntimeError(result.summary)
        return result.summary, "success"
    return "Job handler henuz tanimli degil.", "skipped"


def mark_job_started(db: Session, *, job: ProjectSyncJob) -> ProjectSyncJob:
    job.status = "running"
    job.started_at = datetime.utcnow()
    db.commit()
    db.refresh(job)
    return job


def mark_job_finished(db: Session, *, job: ProjectSyncJob, status: str, summary: str | None = None) -> ProjectSyncJob:
    job.status = status
    job.result_summary = summary
    job.finished_at = datetime.utcnow()
    db.commit()
    db.refresh(job)
    return job
