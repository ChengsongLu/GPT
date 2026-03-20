from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.branch import Branch
from app.models.commit import Commit
from app.schemas.commit import CommitItem, CommitListResponse


async def list_branches(session: AsyncSession) -> list[Branch]:
    result = await session.execute(
        select(Branch).order_by(Branch.is_default.desc(), Branch.name.asc())
    )
    return list(result.scalars().all())


async def list_commits(
    session: AsyncSession,
    branch: str | None,
    author: str | None,
    date_from: datetime | None,
    date_to: datetime | None,
    page: int,
    page_size: int,
) -> CommitListResponse:
    filters = []
    if branch:
        filters.append(Commit.branch_name == branch)
    if author:
        filters.append(func.lower(Commit.author_name).like(f"%{author.lower()}%"))
    if date_from:
        filters.append(Commit.committed_at >= date_from)
    if date_to:
        filters.append(Commit.committed_at <= date_to)

    count_stmt = select(func.count()).select_from(Commit)
    list_stmt = select(Commit)

    if filters:
        count_stmt = count_stmt.where(*filters)
        list_stmt = list_stmt.where(*filters)

    total = await session.scalar(count_stmt)
    result = await session.execute(
        list_stmt.order_by(Commit.committed_at.desc().nullslast(), Commit.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = [CommitItem.model_validate(commit) for commit in result.scalars().all()]
    return CommitListResponse(
        items=items,
        total=total or 0,
        page=page,
        page_size=page_size,
    )
