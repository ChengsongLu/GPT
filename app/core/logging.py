from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOGS_DIR = PROJECT_ROOT / "logs"
SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")


class ShanghaiFormatter(logging.Formatter):
    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:
        dt = datetime.fromtimestamp(record.created, SHANGHAI_TZ)
        if datefmt:
            return dt.strftime(datefmt)
        return dt.strftime("%Y-%m-%d %H:%M:%S")


class ShanghaiDailyFileHandler(logging.FileHandler):
    def __init__(self, logs_dir: Path, encoding: str = "utf-8") -> None:
        self.logs_dir = logs_dir
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self._current_label = self._build_label()
        super().__init__(self._build_filename(self._current_label), encoding=encoding)

    def emit(self, record: logging.LogRecord) -> None:
        current_label = self._build_label()
        if current_label != self._current_label:
            self._switch_file(current_label)
        super().emit(record)

    def _build_label(self) -> str:
        return datetime.now(SHANGHAI_TZ).strftime("%Y_%m_%d")

    def _build_filename(self, label: str) -> str:
        return str(self.logs_dir / f"{label}.log")

    def _switch_file(self, label: str) -> None:
        self.acquire()
        try:
            if self.stream:
                self.stream.close()
                self.stream = None
            self._current_label = label
            self.baseFilename = self._build_filename(label)
            self.stream = self._open()
        finally:
            self.release()


def configure_logging() -> None:
    formatter = ShanghaiFormatter(
        fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    file_handler = ShanghaiDailyFileHandler(LOGS_DIR)
    file_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(stream_handler)
    root_logger.addHandler(file_handler)

    for logger_name in ("uvicorn", "uvicorn.error", "uvicorn.access", "fastapi"):
        logger = logging.getLogger(logger_name)
        logger.handlers.clear()
        logger.propagate = True
        logger.setLevel(logging.INFO)

    logging.getLogger("httpx").setLevel(logging.INFO)
