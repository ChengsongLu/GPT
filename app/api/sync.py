from fastapi import APIRouter, Depends, HTTPException
from httpx import HTTPError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.schemas.sync import BranchSyncResponse, CommitSyncResponse
from app.services.gitlab_client import GitLabConfigError
from app.services.sync_service import sync_branches, sync_commits

router = APIRouter()


@router.post("/sync/branches", response_model=BranchSyncResponse)
async def trigger_branch_sync(
    session: AsyncSession = Depends(get_db_session),
) -> BranchSyncResponse:
    try:
        return await sync_branches(session)
    except GitLabConfigError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"GitLab 请求失败: {exc}") from exc


@router.post("/sync/commits", response_model=CommitSyncResponse)
async def trigger_commit_sync(
    session: AsyncSession = Depends(get_db_session),
) -> CommitSyncResponse:
    try:
        return await sync_commits(session)
    except GitLabConfigError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"GitLab 请求失败: {exc}") from exc
