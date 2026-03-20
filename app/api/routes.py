from fastapi import APIRouter

from app.api.commits import router as commits_router
from app.api import pages
from app.api.health import router as health_router
from app.api.settings import router as settings_router
from app.api.sync import router as sync_router

router = APIRouter()
router.include_router(pages.router)
router.include_router(health_router, tags=["health"])
router.include_router(settings_router, prefix="/api", tags=["settings"])
router.include_router(sync_router, prefix="/api", tags=["sync"])
router.include_router(commits_router, prefix="/api", tags=["commits"])
