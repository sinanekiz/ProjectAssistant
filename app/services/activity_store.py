from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[2]
RUNTIME_DIR = ROOT_DIR / "runtime"
ACTIVITY_FILE_PATH = RUNTIME_DIR / "activity.jsonl"
QUESTIONS_FILE_PATH = RUNTIME_DIR / "questions.jsonl"


def ensure_runtime_dir() -> None:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)


def append_activity(event_type: str, title: str, payload: dict[str, Any] | None = None) -> None:
    ensure_runtime_dir()
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": event_type,
        "title": title,
        "payload": payload or {},
    }
    with ACTIVITY_FILE_PATH.open("a", encoding="utf-8") as file_handle:
        file_handle.write(json.dumps(entry, ensure_ascii=True) + "\n")


def list_recent_activity(limit: int = 30) -> list[dict[str, Any]]:
    if not ACTIVITY_FILE_PATH.exists():
        return []

    entries: list[dict[str, Any]] = []
    with ACTIVITY_FILE_PATH.open("r", encoding="utf-8") as file_handle:
        for line in file_handle:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return list(reversed(entries[-limit:]))


def append_question(question: str, answer: str) -> None:
    ensure_runtime_dir()
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "question": question,
        "answer": answer,
    }
    with QUESTIONS_FILE_PATH.open("a", encoding="utf-8") as file_handle:
        file_handle.write(json.dumps(entry, ensure_ascii=True) + "\n")


def list_recent_questions(limit: int = 20) -> list[dict[str, Any]]:
    if not QUESTIONS_FILE_PATH.exists():
        return []

    entries: list[dict[str, Any]] = []
    with QUESTIONS_FILE_PATH.open("r", encoding="utf-8") as file_handle:
        for line in file_handle:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return list(reversed(entries[-limit:]))
