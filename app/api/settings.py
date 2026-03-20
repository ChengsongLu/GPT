from fastapi import APIRouter, Body, Depends, HTTPException
from httpx import HTTPError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.schemas.feishu import FeishuConnectionResult, FeishuTestPayload
from app.schemas.settings import (
    AppSettingsRead,
    FeishuSettingsPayload,
    GitLabConnectionResult,
    GitLabSettingsPayload,
    GitLabTestPayload,
)
from app.services.feishu_client import FeishuClient, FeishuConfigError
from app.services.feishu_service import test_feishu_connection_from_settings
from app.services.gitlab_client import GitLabClient, GitLabConfigError
from app.services.settings_service import get_or_create_settings, update_settings

router = APIRouter()


@router.get("/settings", response_model=AppSettingsRead)
async def get_settings(session: AsyncSession = Depends(get_db_session)) -> AppSettingsRead:
    settings = await get_or_create_settings(session)
    return AppSettingsRead.model_validate(settings)


@router.post("/settings/gitlab", response_model=AppSettingsRead)
async def save_gitlab_settings(
    payload: GitLabSettingsPayload,
    session: AsyncSession = Depends(get_db_session),
) -> AppSettingsRead:
    settings = await update_settings(session, payload.model_dump(exclude_none=True))
    return AppSettingsRead.model_validate(settings)


@router.post("/settings/feishu", response_model=AppSettingsRead)
async def save_feishu_settings(
    payload: FeishuSettingsPayload,
    session: AsyncSession = Depends(get_db_session),
) -> AppSettingsRead:
    settings = await update_settings(session, payload.model_dump(exclude_none=True))
    return AppSettingsRead.model_validate(settings)


@router.post("/settings/test-gitlab", response_model=GitLabConnectionResult)
async def test_gitlab_connection(
    payload: GitLabTestPayload | None = Body(default=None),
    session: AsyncSession = Depends(get_db_session),
) -> GitLabConnectionResult:
    try:
        if payload is None:
            settings = await get_or_create_settings(session)
            client = GitLabClient.from_settings(settings)
        else:
            client = GitLabClient.from_values(
                base_url=payload.gitlab_base_url,
                token=payload.gitlab_token,
                project_ref=payload.gitlab_project_ref,
            )

        async with client:
            project = await client.fetch_project()
    except GitLabConfigError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"GitLab 请求失败: {exc}") from exc

    return GitLabConnectionResult(
        ok=True,
        project_id=project["id"],
        project_name=project["name"],
        project_path=project["path_with_namespace"],
        default_branch=project.get("default_branch"),
        web_url=project.get("web_url"),
    )


@router.post("/settings/test-feishu", response_model=FeishuConnectionResult)
async def test_feishu_connection(
    payload: FeishuTestPayload | None = Body(default=None),
    session: AsyncSession = Depends(get_db_session),
) -> FeishuConnectionResult:
    try:
        if payload is None:
            return await test_feishu_connection_from_settings(session)

        async with FeishuClient.from_values(
            app_id=payload.feishu_app_id,
            app_secret=payload.feishu_app_secret,
            base_url=payload.feishu_base_url,
            bitable_app_token=payload.feishu_bitable_app_token,
            bitable_table_id=payload.feishu_bitable_table_id,
        ) as client:
            records = await client.list_records(page_size=1)
            return FeishuConnectionResult(
                ok=True,
                app_token=client.config.bitable_app_token,
                table_id=client.config.bitable_table_id,
                sample_record_count=len(records),
            )
    except FeishuConfigError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"飞书请求失败: {exc}") from exc
