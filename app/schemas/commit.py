from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CommitItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    branch_name: str
    commit_sha: str
    author_name: str | None
    author_email: str | None
    committed_at: datetime | None
    title: str | None
    message: str | None
    web_url: str | None


class CommitListResponse(BaseModel):
    items: list[CommitItem]
    total: int
    page: int
    page_size: int
