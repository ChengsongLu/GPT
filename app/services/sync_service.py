from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.branch import Branch
from app.models.commit import Commit
from app.schemas.sync import BranchItem, BranchSyncResponse, CommitSyncResponse
from app.services.gitlab_client import GitLabClient
from app.services.settings_service import get_or_create_settings

logger = logging.getLogger(__name__)


def parse_gitlab_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


async def sync_branches(session: AsyncSession) -> BranchSyncResponse:
    settings = await get_or_create_settings(session)
    logger.info("sync_branches_started project_ref=%s", settings.gitlab_project_ref)

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
    logger.info(
        "sync_branches_finished project_ref=%s synced_count=%s default_branch=%s branches=%s",
        settings.gitlab_project_ref,
        len(rows),
        project.get("default_branch"),
        [branch.name for branch in rows],
    )
    return BranchSyncResponse(
        synced_count=len(rows),
        default_branch=project.get("default_branch"),
        branches=[BranchItem.model_validate(branch) for branch in rows],
    )


async def sync_commits(session: AsyncSession) -> CommitSyncResponse:
    return await sync_commits_with_mode(session, full_sync=False)


async def sync_commits_with_mode(
    session: AsyncSession,
    *,
    full_sync: bool,
) -> CommitSyncResponse:
    settings = await get_or_create_settings(session)
    logger.info(
        "sync_commits_started project_ref=%s mode=%s",
        settings.gitlab_project_ref,
        "full" if full_sync else "incremental",
    )

    branch_result = await session.execute(
        select(Branch).order_by(Branch.is_default.desc(), Branch.name.asc())
    )
    branches = list(branch_result.scalars().all())
    if not branches:
        await sync_branches(session)
        branch_result = await session.execute(
            select(Branch).order_by(Branch.is_default.desc(), Branch.name.asc())
        )
        branches = list(branch_result.scalars().all())

    now = datetime.now(UTC)
    commit_count = 0

    async with GitLabClient.from_settings(settings) as client:
        for branch in branches:
            since = None if full_sync else branch.last_synced_at
            branch_added = 0
            logger.info(
                "sync_commits_branch_started branch=%s since=%s",
                branch.name,
                since.isoformat() if since else "full-history",
            )
            async for payload in client.iter_commits(branch.name, since=since):
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
                branch_added += 1

            branch.last_synced_at = now
            session.add(branch)
            await session.commit()
            logger.info(
                "sync_commits_branch_finished branch=%s added_commits=%s synced_at=%s",
                branch.name,
                branch_added,
                now.isoformat(),
            )

    logger.info(
        "sync_commits_finished project_ref=%s mode=%s branch_count=%s commit_count=%s synced_at=%s",
        settings.gitlab_project_ref,
        "full" if full_sync else "incremental",
        len(branches),
        commit_count,
        now.isoformat(),
    )
    return CommitSyncResponse(
        branch_count=len(branches),
        commit_count=commit_count,
        synced_at=now,
    )
