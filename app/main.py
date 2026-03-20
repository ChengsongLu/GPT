from contextlib import asynccontextmanager
import logging
import json
from time import perf_counter

from fastapi import FastAPI
from fastapi import Request
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.core.config import settings
from app.core.logging import configure_logging
from app.db.session import init_db
from app.services.scheduler_service import start_scheduler, stop_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    await init_db()
    await start_scheduler()
    try:
        yield
    finally:
        await stop_scheduler()


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.include_router(router)

request_logger = logging.getLogger("app.http")
SENSITIVE_KEYS = ("token", "secret", "key", "password", "authorization")


def redact_value(value):
    if isinstance(value, dict):
        redacted = {}
        for key, item in value.items():
            if any(marker in key.lower() for marker in SENSITIVE_KEYS):
                redacted[key] = "***REDACTED***"
            else:
                redacted[key] = redact_value(item)
        return redacted
    if isinstance(value, list):
        return [redact_value(item) for item in value]
    return value


def build_request_detail(request: Request, body_bytes: bytes) -> str:
    parts = []
    if request.url.query:
        parts.append(f"query={request.url.query}")

    if body_bytes:
        try:
            payload = json.loads(body_bytes.decode("utf-8"))
            parts.append(f"body={json.dumps(redact_value(payload), ensure_ascii=False)}")
        except (UnicodeDecodeError, json.JSONDecodeError):
            preview = body_bytes.decode("utf-8", errors="replace")
            if len(preview) > 500:
                preview = f"{preview[:497]}..."
            parts.append(f"body={preview}")

    return " ".join(parts) if parts else "-"


@app.middleware("http")
async def log_http_requests(request: Request, call_next):
    started_at = perf_counter()
    client_host = request.client.host if request.client else "-"
    path = request.url.path
    body_bytes = await request.body()
    detail = build_request_detail(request, body_bytes)

    async def receive():
        return {"type": "http.request", "body": body_bytes, "more_body": False}

    request = Request(request.scope, receive)
    request_logger.info(
        "request_start method=%s path=%s client=%s detail=%s",
        request.method,
        path,
        client_host,
        detail,
    )

    try:
        response = await call_next(request)
    except Exception:
        duration_ms = (perf_counter() - started_at) * 1000
        request_logger.exception(
            "request_failed method=%s path=%s client=%s duration_ms=%.2f detail=%s",
            request.method,
            path,
            client_host,
            duration_ms,
            detail,
        )
        raise

    duration_ms = (perf_counter() - started_at) * 1000
    request_logger.info(
        "request_end method=%s path=%s status=%s client=%s duration_ms=%.2f",
        request.method,
        path,
        response.status_code,
        client_host,
        duration_ms,
    )
    return response
