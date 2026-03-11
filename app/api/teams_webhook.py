from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.message_ingest import ingest_teams_message
from app.services.triage import triage_message

router = APIRouter(prefix="/webhooks/teams", tags=["teams"])


@router.post("", status_code=status.HTTP_202_ACCEPTED)
def teams_webhook(payload: dict[str, Any], db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        message, created, reasons, duplicate = ingest_teams_message(db=db, payload=payload)
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=exc.errors())

    triage_result = None
    triage_status = "not_run"
    approval_status = "not_requested"
    if created and message.is_relevant:
        triage_result = triage_message(db=db, message=message)
        triage_status = "stored" if triage_result is not None else "failed_or_skipped"
        if triage_result is not None and triage_result.approval_request is not None:
            approval_status = triage_result.approval_request.status

    response = {
        "status": "accepted",
        "message_id": message.id,
        "is_relevant": message.is_relevant,
        "reasons": reasons,
        "duplicate": duplicate,
        "created": created,
        "triage_status": triage_status,
        "approval_status": approval_status,
    }
    if triage_result is not None:
        response["triage_result_id"] = triage_result.id
        if triage_result.approval_request is not None:
            response["approval_request_id"] = triage_result.approval_request.id
    return response
