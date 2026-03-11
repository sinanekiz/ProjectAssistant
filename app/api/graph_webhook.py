from __future__ import annotations

from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import PlainTextResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.adapters.graph_client import GraphClient
from app.db.models import TeamsMessage
from app.db.session import get_db
from app.logging import get_logger
from app.services.message_ingest import process_graph_notifications
from app.services.triage import triage_message

router = APIRouter(prefix="/webhooks/graph", tags=["graph"])
logger = get_logger(__name__)


@router.post("", status_code=status.HTTP_202_ACCEPTED, response_model=None)
async def graph_webhook(
    request: Request,
    validation_token: str | None = Query(default=None, alias="validationToken"),
    db: Session = Depends(get_db),
) -> Any:
    if validation_token is not None:
        logger.info("graph_webhook_validation_requested")
        return PlainTextResponse(content=validation_token, status_code=status.HTTP_200_OK)

    try:
        payload = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON payload") from exc

    try:
        results = process_graph_notifications(db=db, payload=payload, graph_client=GraphClient.from_settings())
    except ValidationError as exc:
        logger.warning("graph_webhook_invalid_payload", extra={"errors": exc.errors()})
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=exc.errors())

    triage_started_count = 0
    for result in results:
        if not result.is_relevant or result.message_id is None:
            continue

        message = db.get(TeamsMessage, result.message_id)
        if message is None:
            continue

        triage_started_count += 1
        triage_message(db=db, message=message)

    processed_count = sum(1 for result in results if result.status in {"stored", "duplicate"})
    stored_count = sum(1 for result in results if result.status == "stored")
    return {
        "status": "accepted",
        "notification_count": len(results),
        "processed_count": processed_count,
        "stored_count": stored_count,
        "triage_started_count": triage_started_count,
        "results": [asdict(result) for result in results],
    }
