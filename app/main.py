from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.api.control_panel import router as control_panel_router
from app.api.graph_webhook import router as graph_webhook_router
from app.api.health import router as health_router
from app.api.projects import router as projects_router
from app.api.telegram_webhook import router as telegram_webhook_router
from app.api.teams_webhook import router as teams_webhook_router
from app.config import get_settings
from app.logging import configure_logging, get_logger
from app.services.telegram_polling import refresh_telegram_polling_state, stop_telegram_polling

configure_logging()
logger = get_logger(__name__)
STATIC_DIR = Path(__file__).resolve().parent / "ui" / "static"


@asynccontextmanager
async def lifespan(application: FastAPI):
    await refresh_telegram_polling_state()
    try:
        yield
    finally:
        await stop_telegram_polling()


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(title=settings.app_name, lifespan=lifespan)
    application.add_middleware(
        SessionMiddleware,
        secret_key=settings.panel_session_secret or settings.panel_login_password or "projectassistant-dev-session",
        same_site="lax",
        https_only=settings.app_env != "local",
    )
    application.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    application.include_router(control_panel_router)
    application.include_router(projects_router)
    application.include_router(health_router)
    application.include_router(graph_webhook_router)
    application.include_router(teams_webhook_router)
    application.include_router(telegram_webhook_router)
    logger.info("application_initialized", extra={"environment": settings.app_env})
    return application


app = create_app()
