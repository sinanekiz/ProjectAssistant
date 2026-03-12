from __future__ import annotations

import hashlib
import io
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Project, ProjectContextDocument, ProjectContextEntry
from app.logging import get_logger

try:  # pragma: no cover - optional dependency for PDF parsing
    from pypdf import PdfReader
except Exception:  # pragma: no cover
    PdfReader = None

logger = get_logger(__name__)

MAX_CONTEXT_CHARS = 20000
_WORD_SPLIT_RE = re.compile(r"(?<!^)(?=[A-Z])")
_NON_WORD_RE = re.compile(r"[^a-z0-9]+")


@dataclass(slots=True)
class ContextImportResult:
    imported: int
    updated: int
    skipped: int
    errors: list[str]


@dataclass(slots=True)
class ContextUpload:
    filename: str
    payload: bytes
    content_type: str | None = None


def suggest_context_prefix(project: Project) -> str:
    name = project.name.strip()
    if not name:
        return project.slug
    dotted = ".".join(part for part in re.split(r"[\s_-]+", name) if part)
    return dotted or project.slug


def infer_context_prefixes(project: Project) -> list[str]:
    prefixes = {project.slug}
    if project.name.strip():
        prefixes.add(project.name.strip())
        prefixes.add(project.name.strip().replace(" ", "."))
    dotted = suggest_context_prefix(project)
    if dotted:
        prefixes.add(dotted)
    normalized = [prefix for prefix in prefixes if prefix]
    return list(dict.fromkeys(normalized))


def discover_context_files(contexts_dir: Path, prefixes: list[str] | None = None) -> list[Path]:
    if not contexts_dir.exists():
        return []
    files = [path for path in contexts_dir.iterdir() if path.suffix.lower() in {".md", ".txt", ".pdf"} and path.is_file()]
    if not prefixes:
        return sorted(files)
    matched: list[Path] = []
    for path in files:
        stem = path.stem.lower()
        if any(stem.startswith(prefix.lower()) for prefix in prefixes):
            matched.append(path)
    return sorted(matched)


def import_contexts_from_folder(
    db: Session,
    *,
    project: Project,
    contexts_dir: Path,
    prefix_override: str | None = None,
) -> ContextImportResult:
    prefixes = [prefix_override] if prefix_override else infer_context_prefixes(project)
    files = discover_context_files(contexts_dir, prefixes)
    imported = updated = skipped = 0
    errors: list[str] = []
    for path in files:
        try:
            entry = _build_context_entry_from_path(project=project, path=path, contexts_dir=contexts_dir, prefix=prefix_override)
            if entry is None:
                skipped += 1
                continue
            existing = _find_existing_entry(db, project, entry.source_ref)
            if existing is None:
                db.add(entry)
                imported += 1
            else:
                existing.title = entry.title
                existing.section = entry.section
                existing.content = entry.content
                existing.source_type = entry.source_type
                updated += 1
        except Exception as exc:  # pragma: no cover - defensive guard
            errors.append(f"{path.name}: {exc}")
    if imported or updated:
        db.commit()
    return ContextImportResult(imported=imported, updated=updated, skipped=skipped, errors=errors)


def import_contexts_from_uploads(
    db: Session,
    *,
    project: Project,
    uploads: list[ContextUpload],
    section: str,
    source_type: str,
) -> ContextImportResult:
    imported = updated = skipped = 0
    errors: list[str] = []
    for upload in uploads:
        try:
            entry = _build_context_entry_from_upload(
                project=project,
                filename=upload.filename,
                payload=upload.payload,
                section=section,
                source_type=source_type,
            )
            if entry is None:
                skipped += 1
                continue
            existing = _find_existing_entry(db, project, entry.source_ref)
            if existing is None:
                db.add(entry)
                imported += 1
            else:
                existing.title = entry.title
                existing.section = entry.section
                existing.content = entry.content
                existing.source_type = entry.source_type
                updated += 1

            _upsert_context_document(
                db,
                project=project,
                filename=upload.filename,
                payload=upload.payload,
                content_type=upload.content_type,
                source_type=source_type,
                source_ref=entry.source_ref,
            )
        except Exception as exc:
            errors.append(f"{upload.filename}: {exc}")
    if imported or updated:
        db.commit()
    return ContextImportResult(imported=imported, updated=updated, skipped=skipped, errors=errors)


def _find_existing_entry(db: Session, project: Project, source_ref: str | None) -> ProjectContextEntry | None:
    if not source_ref:
        return None
    return db.scalar(
        select(ProjectContextEntry).where(
            ProjectContextEntry.project_id == project.id,
            ProjectContextEntry.source_ref == source_ref,
        )
    )


def _find_existing_document(db: Session, project: Project, checksum: str, filename: str) -> ProjectContextDocument | None:
    return db.scalar(
        select(ProjectContextDocument).where(
            ProjectContextDocument.project_id == project.id,
            ProjectContextDocument.checksum == checksum,
            ProjectContextDocument.filename == filename,
        )
    )


def _upsert_context_document(
    db: Session,
    *,
    project: Project,
    filename: str,
    payload: bytes,
    content_type: str | None,
    source_type: str,
    source_ref: str | None,
) -> None:
    checksum = _compute_checksum(payload)
    existing = _find_existing_document(db, project, checksum, filename)
    if existing is None:
        document = ProjectContextDocument(
            project_id=project.id,
            filename=filename,
            content_type=content_type,
            size_bytes=len(payload),
            checksum=checksum,
            source_type=source_type or "upload",
            source_ref=source_ref,
            extracted_at=datetime.utcnow(),
        )
        db.add(document)
    else:
        existing.content_type = content_type
        existing.size_bytes = len(payload)
        existing.source_type = source_type or existing.source_type
        existing.source_ref = source_ref
        existing.extracted_at = datetime.utcnow()


def _build_context_entry_from_path(
    *,
    project: Project,
    path: Path,
    contexts_dir: Path,
    prefix: str | None,
) -> ProjectContextEntry | None:
    content = _read_file_text(path)
    if not content.strip():
        return None
    title = _extract_title_from_markdown(content) or _humanize_title(_strip_prefix(path.stem, prefix))
    section = _section_from_name(_strip_prefix(path.stem, prefix))
    source_ref = str(path.relative_to(contexts_dir)) if contexts_dir in path.parents else str(path)
    return ProjectContextEntry(
        project_id=project.id,
        title=title,
        section=section,
        content=_truncate_content(content),
        source_type="context-file",
        source_ref=source_ref,
    )


def _build_context_entry_from_upload(
    *,
    project: Project,
    filename: str,
    payload: bytes,
    section: str,
    source_type: str,
) -> ProjectContextEntry | None:
    content = _read_payload_text(filename, payload)
    if not content.strip():
        return None
    title = _extract_title_from_markdown(content) or _humanize_title(Path(filename).stem)
    return ProjectContextEntry(
        project_id=project.id,
        title=title,
        section=section.strip() or "general",
        content=_truncate_content(content),
        source_type=source_type.strip() or "upload",
        source_ref=f"upload:{filename}",
    )


def _read_file_text(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        return _read_pdf_text(path)
    return path.read_text(encoding="utf-8", errors="ignore")


def _read_payload_text(filename: str, payload: bytes) -> str:
    if Path(filename).suffix.lower() == ".pdf":
        return _read_pdf_payload(payload)
    return payload.decode("utf-8", errors="ignore")


def _read_pdf_text(path: Path) -> str:
    if PdfReader is None:
        raise RuntimeError("PDF parsing icin pypdf yuklu degil.")
    reader = PdfReader(str(path))
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(pages)


def _read_pdf_payload(payload: bytes) -> str:
    if PdfReader is None:
        raise RuntimeError("PDF parsing icin pypdf yuklu degil.")
    reader = PdfReader(io.BytesIO(payload))
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(pages)


def _extract_title_from_markdown(content: str) -> str | None:
    for line in content.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return None


def _strip_prefix(stem: str, prefix: str | None) -> str:
    if not prefix:
        return stem
    lowered = stem.lower()
    pref = prefix.lower()
    if lowered.startswith(pref):
        remainder = stem[len(prefix) :].lstrip("._- ")
        return remainder or stem
    return stem


def _section_from_name(value: str) -> str:
    cleaned = _NON_WORD_RE.sub("_", value.strip().lower()).strip("_")
    return cleaned or "general"


def _humanize_title(value: str) -> str:
    if not value:
        return "Context"
    value = value.replace("_", " ").replace("-", " ")
    value = " ".join(_WORD_SPLIT_RE.split(value))
    return value.strip().title()


def _truncate_content(content: str) -> str:
    if len(content) <= MAX_CONTEXT_CHARS:
        return content
    return content[:MAX_CONTEXT_CHARS].rstrip() + "\n\n[truncated]"


def _compute_checksum(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()
