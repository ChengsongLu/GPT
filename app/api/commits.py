from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.schemas.commit import CommitListResponse
from app.schemas.sync import BranchItem
from app.services.commit_service import list_branches, list_commits

router = APIRouter()


@router.get("/branches", response_model=list[BranchItem])
async def get_branches(session: AsyncSession = Depends(get_db_session)) -> list[BranchItem]:
    branches = await list_branches(session)
    return [BranchItem.model_validate(branch) for branch in branches]


@router.get("/commits", response_model=CommitListResponse)
async def get_commits(
    branch: str | None = None,
    author: str | None = None,
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_db_session),
) -> CommitListResponse:
    return await list_commits(
        session=session,
        branch=branch,
        author=author,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size,
    )
