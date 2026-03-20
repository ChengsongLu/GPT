from fastapi import APIRouter, HTTPException, Query

from app.schemas.log import LogContentResponse, LogFileListResponse
from app.services.log_service import get_log_content, list_log_files

router = APIRouter()


@router.get("/logs", response_model=LogFileListResponse)
async def get_logs() -> LogFileListResponse:
    return await list_log_files()


@router.get("/logs/content", response_model=LogContentResponse)
async def get_logs_content(
    log_date: str | None = Query(default=None),
    limit: int = Query(default=200, ge=20, le=2000),
) -> LogContentResponse:
    try:
        return await get_log_content(log_date=log_date, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
