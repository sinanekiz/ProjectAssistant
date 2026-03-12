from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Project, ProjectContextEntry


def upsert_context_entry(
    db: Session,
    *,
    project: Project,
    title: str,
    section: str,
    content: str,
    source_type: str,
    source_ref: str,
) -> tuple[ProjectContextEntry, bool]:
    entry = db.scalar(
        select(ProjectContextEntry).where(
            ProjectContextEntry.project_id == project.id,
            ProjectContextEntry.source_ref == source_ref,
        )
    )
    if entry is None:
        entry = ProjectContextEntry(
            project_id=project.id,
            title=title,
            section=section,
            content=content,
            source_type=source_type,
            source_ref=source_ref,
        )
        db.add(entry)
        created = True
    else:
        entry.title = title
        entry.section = section
        entry.content = content
        entry.source_type = source_type
        created = False
    db.commit()
    db.refresh(entry)
    return entry, created
