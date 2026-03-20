import os

import uvicorn

from app.core.config import settings


if __name__ == "__main__":
    reload_enabled = os.getenv("GPT_RELOAD", "1") not in {"0", "false", "False"}
    uvicorn.run(
        "app.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=reload_enabled,
        reload_dirs=["app", "mock"] if reload_enabled else None,
    )
