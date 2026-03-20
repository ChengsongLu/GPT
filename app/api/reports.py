from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.llm import LLMConfigError, LLMRequestError
from app.schemas.report import DailyReportGenerationResponse, DailyReportListResponse, ReportDateListResponse
from app.services.report_service import (
    generate_daily_reports,
    list_branch_reports,
    list_project_reports,
    list_report_dates,
)

router = APIRouter()


@router.get("/reports", response_model=DailyReportListResponse)
async def get_branch_reports(
    branch: str | None = Query(default=None),
    report_date: date | None = Query(default=None),
    session: AsyncSession = Depends(get_db_session),
) -> DailyReportListResponse:
    return await list_branch_reports(session=session, branch=branch, report_date=report_date)


@router.get("/reports/project-daily", response_model=DailyReportListResponse)
async def get_project_reports(
    report_date: date | None = Query(default=None),
    session: AsyncSession = Depends(get_db_session),
) -> DailyReportListResponse:
    return await list_project_reports(session, report_date=report_date)


@router.get("/reports/dates", response_model=ReportDateListResponse)
async def get_report_dates(
    session: AsyncSession = Depends(get_db_session),
) -> ReportDateListResponse:
    return await list_report_dates(session)


@router.post("/reports/generate-daily", response_model=DailyReportGenerationResponse)
async def trigger_daily_report_generation(
    report_date: date | None = Query(default=None),
    session: AsyncSession = Depends(get_db_session),
) -> DailyReportGenerationResponse:
    try:
        return await generate_daily_reports(session, report_date=report_date)
    except LLMConfigError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LLMRequestError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
