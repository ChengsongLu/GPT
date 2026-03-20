from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.branch import Branch
from app.models.commit import Commit
from app.schemas.sync import BranchItem, BranchSyncResponse, CommitSyncResponse
from app.services.gitlab_client import GitLabClient
from app.services.settings_service import get_or_create_settings


def parse_gitlab_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


async def sync_branches(session: AsyncSession) -> BranchSyncResponse:
    settings = await get_or_create_settings(session)

    async with GitLabClient.from_settings(settings) as client:
        project = await client.fetch_project()
        branch_payloads = await client.fetch_branches()

    existing_result = await session.execute(select(Branch))
    existing_by_name = {branch.name: branch for branch in existing_result.scalars().all()}

    branches: list[Branch] = []
    for payload in branch_payloads:
        branch = existing_by_name.get(payload["name"])
        if branch is None:
            branch = Branch(name=payload["name"])
        branch.is_default = bool(payload.get("default"))
        session.add(branch)
        branches.append(branch)

    await session.commit()

    refreshed = await session.execute(
        select(Branch).order_by(Branch.is_default.desc(), Branch.name.asc())
    )
    rows = list(refreshed.scalars().all())
    return BranchSyncResponse(
        synced_count=len(rows),
        default_branch=project.get("default_branch"),
        branches=[BranchItem.model_validate(branch) for branch in rows],
    )


async def sync_commits(session: AsyncSession) -> CommitSyncResponse:
    settings = await get_or_create_settings(session)

    branch_result = await session.execute(
        select(Branch).order_by(Branch.is_default.desc(), Branch.name.asc())
    )
    branches = list(branch_result.scalars().all())
    if not branches:
        branch_sync = await sync_branches(session)
        branches = [
            Branch(
                id=item.id,
                name=item.name,
                is_default=item.is_default,
                last_synced_at=item.last_synced_at,
            )
            for item in branch_sync.branches
        ]
        branch_result = await session.execute(
            select(Branch).order_by(Branch.is_default.desc(), Branch.name.asc())
        )
        branches = list(branch_result.scalars().all())

    now = datetime.now(UTC)
    commit_count = 0

    async with GitLabClient.from_settings(settings) as client:
        for branch in branches:
            async for payload in client.iter_commits(branch.name, since=branch.last_synced_at):
                sha = payload["id"]
                existing = await session.execute(
                    select(Commit.id).where(
                        Commit.branch_name == branch.name,
                        Commit.commit_sha == sha,
                    )
                )
                if existing.scalar_one_or_none() is not None:
                    continue

                commit = Commit(
                    branch_name=branch.name,
                    commit_sha=sha,
                    author_name=payload.get("author_name"),
                    author_email=payload.get("author_email"),
                    committed_at=parse_gitlab_datetime(payload.get("committed_date")),
                    title=payload.get("title"),
                    message=payload.get("message"),
                    web_url=payload.get("web_url"),
                    raw_payload=payload,
                )
                session.add(commit)
                commit_count += 1

            branch.last_synced_at = now
            session.add(branch)
            await session.commit()

    return CommitSyncResponse(
        branch_count=len(branches),
        commit_count=commit_count,
        synced_at=now,
    )
