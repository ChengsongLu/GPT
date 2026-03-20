from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class DailyReportItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    report_date: date
    report_type: str
    branch_name: str | None
    content: str
    status: str
    sent_at: datetime | None
    created_at: datetime


class DailyReportListResponse(BaseModel):
    report_date: date | None
    items: list[DailyReportItem]
    branch_names: list[str]


class DailyReportGenerationResponse(BaseModel):
    report_date: date
    commit_count: int
    branch_count: int
    project_report: DailyReportItem
    branch_reports: list[DailyReportItem]


class ReportDateItem(BaseModel):
    report_date: date
    commit_count: int
    has_reports: bool


class ReportDateListResponse(BaseModel):
    selected_date: date | None
    items: list[ReportDateItem]
