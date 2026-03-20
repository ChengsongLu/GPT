from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class GitLabSettingsPayload(BaseModel):
    gitlab_base_url: str = Field(min_length=1)
    gitlab_token: str = Field(min_length=1)
    gitlab_project_ref: str = Field(min_length=1)
    sync_interval_minutes: int = Field(default=15, ge=1, le=1440)
    timezone: str = Field(default="Asia/Shanghai", min_length=1)


class GitLabTestPayload(BaseModel):
    gitlab_base_url: str = Field(min_length=1)
    gitlab_token: str = Field(min_length=1)
    gitlab_project_ref: str = Field(min_length=1)


class FeishuSettingsPayload(BaseModel):
    feishu_app_id: str = Field(min_length=1)
    feishu_app_secret: str = Field(min_length=1)
    feishu_bitable_app_token: str = Field(min_length=1)
    feishu_bitable_table_id: str = Field(min_length=1)
    feishu_chat_id: str = Field(min_length=1)


class AppSettingsRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    gitlab_base_url: str | None
    gitlab_token: str | None
    gitlab_project_ref: str | None
    sync_interval_minutes: int
    timezone: str
    feishu_app_id: str | None
    feishu_app_secret: str | None
    feishu_bitable_app_token: str | None
    feishu_bitable_table_id: str | None
    feishu_chat_id: str | None
    created_at: datetime
    updated_at: datetime


class GitLabConnectionResult(BaseModel):
    ok: bool
    project_id: int
    project_name: str
    project_path: str
    default_branch: str | None
    web_url: str | None
