from __future__ import annotations

from pathlib import Path

from sqlalchemy import select

from app.db.models import Project, ProjectContextEntry, ProjectContextDocument
from app.services.context_ingest import ContextUpload, import_contexts_from_folder, import_contexts_from_uploads


def test_import_contexts_from_folder(session_factory, tmp_path: Path) -> None:
    db = session_factory()
    project = Project(name="GridBox HeadEnd", slug="gridbox-headend", ownership_type="company")
    db.add(project)
    db.commit()
    db.refresh(project)

    contexts_dir = tmp_path / "contexts"
    contexts_dir.mkdir()
    (contexts_dir / "GridBox.HeadEnd.Index.md").write_text("# Index\nRoot context", encoding="utf-8")

    result = import_contexts_from_folder(db, project=project, contexts_dir=contexts_dir)
    assert result.imported == 1

    entry = db.scalar(select(ProjectContextEntry).where(ProjectContextEntry.project_id == project.id))
    assert entry is not None
    assert entry.title == "Index"
    assert entry.section == "index"


def test_import_contexts_from_uploads(session_factory) -> None:
    db = session_factory()
    project = Project(name="Mobitolya", slug="mobitolya", ownership_type="personal")
    db.add(project)
    db.commit()
    db.refresh(project)

    uploads = [ContextUpload(filename="notes.txt", payload=b"Support flow notes", content_type="text/plain")]
    result = import_contexts_from_uploads(db, project=project, uploads=uploads, section="support", source_type="upload")
    assert result.imported == 1

    entry = db.scalar(select(ProjectContextEntry).where(ProjectContextEntry.project_id == project.id))
    assert entry is not None
    assert entry.section == "support"
    assert "Support flow" in entry.content

    doc = db.scalar(select(ProjectContextDocument).where(ProjectContextDocument.project_id == project.id))
    assert doc is not None
    assert doc.filename == "notes.txt"
