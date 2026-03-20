from datetime import datetime

from pydantic import BaseModel


class LogFileItem(BaseModel):
    log_date: str
    filename: str
    size_bytes: int
    modified_at: datetime


class LogFileListResponse(BaseModel):
    selected_date: str | None
    items: list[LogFileItem]


class LogContentResponse(BaseModel):
    log_date: str
    filename: str
    line_count: int
    content: str
