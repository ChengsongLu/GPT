from datetime import datetime

from pydantic import BaseModel, ConfigDict


class BranchItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    is_default: bool
    last_synced_at: datetime | None


class BranchSyncResponse(BaseModel):
    synced_count: int
    default_branch: str | None
    branches: list[BranchItem]


class CommitSyncResponse(BaseModel):
    branch_count: int
    commit_count: int
    synced_at: datetime
