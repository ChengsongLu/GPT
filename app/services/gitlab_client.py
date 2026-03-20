from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote

import httpx

from app.models.settings import AppSettings


class GitLabConfigError(ValueError):
    pass


@dataclass(slots=True)
class GitLabConfig:
    base_url: str
    token: str
    project_ref: str


class GitLabClient:
    def __init__(self, config: GitLabConfig) -> None:
        self.config = config
        self._client = httpx.AsyncClient(
            base_url=self.config.base_url.rstrip("/"),
            headers={"PRIVATE-TOKEN": self.config.token},
            timeout=30.0,
        )

    @classmethod
    def from_settings(cls, settings: AppSettings) -> "GitLabClient":
        return cls.from_values(
            base_url=settings.gitlab_base_url,
            token=settings.gitlab_token,
            project_ref=settings.gitlab_project_ref,
        )

    @classmethod
    def from_values(
        cls,
        *,
        base_url: str | None,
        token: str | None,
        project_ref: str | None,
    ) -> "GitLabClient":
        base_url = (base_url or "").strip()
        token = (token or "").strip()
        project_ref = (project_ref or "").strip()

        if not base_url:
            raise GitLabConfigError("缺少 GitLab Base URL")
        if not token:
            raise GitLabConfigError("缺少 GitLab Token")
        if not project_ref:
            raise GitLabConfigError("缺少 GitLab Project ID 或路径")

        return cls(
            GitLabConfig(
                base_url=base_url,
                token=token,
                project_ref=project_ref,
            )
        )

    async def __aenter__(self) -> "GitLabClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._client.aclose()

    @property
    def project_path(self) -> str:
        return quote(self.config.project_ref, safe="")

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> httpx.Response:
        response = await self._client.get(path, params=params)
        response.raise_for_status()
        return response

    async def fetch_project(self) -> dict[str, Any]:
        response = await self._get(f"/api/v4/projects/{self.project_path}")
        return response.json()

    async def fetch_branches(self) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        page = 1
        while True:
            response = await self._get(
                f"/api/v4/projects/{self.project_path}/repository/branches",
                params={"page": page, "per_page": 100},
            )
            chunk = response.json()
            items.extend(chunk)
            if len(chunk) < 100:
                break
            page += 1
        return items

    async def iter_commits(
        self,
        branch_name: str,
        *,
        since: datetime | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        page = 1
        while True:
            params: dict[str, Any] = {
                "ref_name": branch_name,
                "page": page,
                "per_page": 100,
            }
            if since is not None:
                if since.tzinfo is None:
                    since = since.replace(tzinfo=UTC)
                params["since"] = since.astimezone().isoformat()

            response = await self._get(
                f"/api/v4/projects/{self.project_path}/repository/commits",
                params=params,
            )
            chunk = response.json()
            if not chunk:
                break

            for item in chunk:
                yield item

            if len(chunk) < 100:
                break
            page += 1
