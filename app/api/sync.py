from fastapi import APIRouter, Depends, HTTPException
from httpx import HTTPError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.schemas.feishu import ContributorListResponse, ContributorSyncResponse
from app.schemas.sync import BranchSyncResponse, CommitSyncResponse
from app.services.feishu_client import FeishuConfigError
from app.services.feishu_service import list_contributors, sync_feishu_contributors
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


@router.post("/sync/feishu-contributors", response_model=ContributorSyncResponse)
async def trigger_feishu_contributor_sync(
    session: AsyncSession = Depends(get_db_session),
) -> ContributorSyncResponse:
    try:
        return await sync_feishu_contributors(session)
    except FeishuConfigError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"飞书请求失败: {exc}") from exc


@router.get("/contributors", response_model=ContributorListResponse)
async def get_contributors(
    session: AsyncSession = Depends(get_db_session),
) -> ContributorListResponse:
    return await list_contributors(session)
