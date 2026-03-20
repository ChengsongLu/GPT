from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.contributor import Contributor
from app.schemas.feishu import (
    ContributorItem,
    ContributorListResponse,
    ContributorSyncResponse,
    FeishuConnectionResult,
)
from app.services.feishu_client import FeishuClient
from app.services.settings_service import get_or_create_settings


def normalize_feishu_value(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, dict):
        for key in ("text", "name"):
            nested = value.get(key)
            if isinstance(nested, str) and nested.strip():
                return nested.strip()
        return None
    if isinstance(value, list):
        parts = [normalize_feishu_value(item) for item in value]
        merged = ", ".join(part for part in parts if part)
        return merged or None
    return str(value)


def map_record_to_contributor_fields(record: dict[str, Any]) -> dict[str, Any]:
    fields = record.get("fields", {})
    return {
        "name": normalize_feishu_value(fields.get("开发者姓名")) or "未命名成员",
        "gitlab_username": normalize_feishu_value(fields.get("GitLab 用户名")),
        "component": normalize_feishu_value(fields.get("负责组件")),
        "feishu_record_id": record.get("record_id"),
    }


async def test_feishu_connection_from_settings(session: AsyncSession) -> FeishuConnectionResult:
    settings = await get_or_create_settings(session)
    async with FeishuClient.from_settings(settings) as client:
        records = await client.list_records(page_size=1)
        return FeishuConnectionResult(
            ok=True,
            app_token=client.config.bitable_app_token,
            table_id=client.config.bitable_table_id,
            sample_record_count=len(records),
        )


async def sync_feishu_contributors(session: AsyncSession) -> ContributorSyncResponse:
    settings = await get_or_create_settings(session)

    async with FeishuClient.from_settings(settings) as client:
        records = await client.list_records(page_size=100)

    existing_result = await session.execute(select(Contributor))
    existing_by_record_id = {
        contributor.feishu_record_id: contributor
        for contributor in existing_result.scalars().all()
        if contributor.feishu_record_id
    }

    seen_record_ids: set[str] = set()
    for record in records:
        mapped = map_record_to_contributor_fields(record)
        record_id = mapped["feishu_record_id"]
        if not record_id:
            continue

        contributor = existing_by_record_id.get(record_id)
        if contributor is None:
            contributor = Contributor(feishu_record_id=record_id, name=mapped["name"])

        contributor.name = mapped["name"]
        contributor.gitlab_username = mapped["gitlab_username"]
        contributor.component = mapped["component"]
        contributor.is_active = True

        session.add(contributor)
        seen_record_ids.add(record_id)

    for record_id, contributor in existing_by_record_id.items():
        if record_id not in seen_record_ids:
            contributor.is_active = False
            session.add(contributor)

    await session.commit()

    refreshed = await session.execute(
        select(Contributor).order_by(Contributor.is_active.desc(), Contributor.name.asc())
    )
    rows = list(refreshed.scalars().all())
    active_count = sum(1 for contributor in rows if contributor.is_active)

    return ContributorSyncResponse(
        synced_count=len(seen_record_ids),
        active_count=active_count,
        contributors=[ContributorItem.model_validate(contributor) for contributor in rows],
    )


async def list_contributors(session: AsyncSession) -> ContributorListResponse:
    result = await session.execute(
        select(Contributor).order_by(Contributor.is_active.desc(), Contributor.name.asc())
    )
    rows = list(result.scalars().all())
    active_count = sum(1 for contributor in rows if contributor.is_active)

    return ContributorListResponse(
        total_count=len(rows),
        active_count=active_count,
        contributors=[ContributorItem.model_validate(contributor) for contributor in rows],
    )
