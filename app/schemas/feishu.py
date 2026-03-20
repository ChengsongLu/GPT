from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class FeishuTestPayload(BaseModel):
    feishu_app_id: str = Field(min_length=1)
    feishu_app_secret: str = Field(min_length=1)
    feishu_base_url: str = Field(default="https://open.feishu.cn", min_length=1)
    feishu_bitable_app_token: str = Field(min_length=1)
    feishu_bitable_table_id: str = Field(min_length=1)


class FeishuConnectionResult(BaseModel):
    ok: bool
    app_token: str
    table_id: str
    sample_record_count: int


class ContributorItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    gitlab_username: str | None
    component: str | None
    feishu_record_id: str | None
    is_active: bool
    updated_at: datetime


class ContributorSyncResponse(BaseModel):
    synced_count: int
    active_count: int
    contributors: list[ContributorItem]


class ContributorListResponse(BaseModel):
    total_count: int
    active_count: int
    contributors: list[ContributorItem]
