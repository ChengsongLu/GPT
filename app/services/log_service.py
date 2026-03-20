from __future__ import annotations

import asyncio
from collections import deque
from datetime import datetime
from pathlib import Path
import re

from app.core.logging import LOGS_DIR, SHANGHAI_TZ
from app.schemas.log import LogContentResponse, LogFileItem, LogFileListResponse


LOG_DATE_PATTERN = re.compile(r"^\d{4}_\d{2}_\d{2}$")


async def list_log_files() -> LogFileListResponse:
    items = await asyncio.to_thread(_list_log_files_sync)
    selected_date = items[0].log_date if items else None
    return LogFileListResponse(selected_date=selected_date, items=items)


async def get_log_content(log_date: str | None, limit: int = 200) -> LogContentResponse:
    selected_date = log_date or datetime.now(SHANGHAI_TZ).strftime("%Y_%m_%d")
    if not LOG_DATE_PATTERN.fullmatch(selected_date):
        raise ValueError("日志日期格式不正确，应为 YYYY_MM_DD")

    filename = f"{selected_date}.log"
    path = LOGS_DIR / filename
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"未找到日志文件：{filename}")

    safe_limit = min(max(limit, 20), 2000)
    content, line_count = await asyncio.to_thread(_read_tail_sync, path, safe_limit)
    return LogContentResponse(
        log_date=selected_date,
        filename=filename,
        line_count=line_count,
        content=content,
    )


def _list_log_files_sync() -> list[LogFileItem]:
    if not LOGS_DIR.exists():
        return []

    items: list[LogFileItem] = []
    for path in sorted(LOGS_DIR.glob("*.log"), key=lambda item: item.name, reverse=True):
        stat = path.stat()
        modified_at = datetime.fromtimestamp(stat.st_mtime, SHANGHAI_TZ)
        items.append(
            LogFileItem(
                log_date=path.stem,
                filename=path.name,
                size_bytes=stat.st_size,
                modified_at=modified_at,
            )
        )
    return items


def _read_tail_sync(path: Path, limit: int) -> tuple[str, int]:
    buffer: deque[str] = deque(maxlen=limit)
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            buffer.append(line.rstrip("\n"))
    content = "\n".join(buffer)
    return content, len(buffer)
