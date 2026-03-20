from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote

from fastapi import FastAPI, HTTPException, Query, Request

FIXTURES_ROOT = Path(__file__).resolve().parent / "fixtures"


@dataclass(slots=True)
class MockGitLabDataset:
    project: dict
    branches: list[dict]
    commits_by_branch: dict[str, list[dict]]

    @property
    def project_ref(self) -> str:
        return self.project["path_with_namespace"]


def load_dataset(scenario: str) -> MockGitLabDataset:
    scenario_dir = FIXTURES_ROOT / scenario
    if not scenario_dir.exists():
        raise FileNotFoundError(f"未知 mock 场景: {scenario}")

    project = json.loads((scenario_dir / "project.json").read_text(encoding="utf-8"))
    branches = json.loads((scenario_dir / "branches.json").read_text(encoding="utf-8"))
    commits_by_branch = json.loads((scenario_dir / "commits.json").read_text(encoding="utf-8"))
    return MockGitLabDataset(project=project, branches=branches, commits_by_branch=commits_by_branch)


def parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def create_mock_gitlab_app(
    *,
    scenario: str = "basic",
    delay_ms: int = 0,
    fail_endpoint: str | None = None,
    fail_status: int = 500,
) -> FastAPI:
    dataset = load_dataset(scenario)
    app = FastAPI(title=f"Mock GitLab ({scenario})")

    async def maybe_delay() -> None:
        if delay_ms > 0:
            await asyncio.sleep(delay_ms / 1000)

    def assert_project_ref(project_ref: str) -> None:
        decoded = unquote(project_ref)
        if decoded != dataset.project_ref:
            raise HTTPException(status_code=404, detail=f"未知项目: {decoded}")

    def maybe_fail(endpoint: str) -> None:
        if fail_endpoint == endpoint:
            raise HTTPException(status_code=fail_status, detail=f"Mock forced failure: {endpoint}")

    @app.get("/health")
    async def health() -> dict[str, str | int]:
        return {"status": "ok", "scenario": scenario, "delay_ms": delay_ms}

    @app.get("/api/v4/projects/{project_ref:path}/repository/branches")
    async def get_branches(project_ref: str) -> list[dict]:
        maybe_fail("branches")
        assert_project_ref(project_ref)
        await maybe_delay()
        return dataset.branches

    @app.get("/api/v4/projects/{project_ref:path}/repository/commits")
    async def get_commits(
        request: Request,
        project_ref: str,
        ref_name: str = Query(...),
        since: str | None = Query(default=None),
        page: int = Query(default=1, ge=1),
        per_page: int = Query(default=100, ge=1, le=100),
    ) -> list[dict]:
        maybe_fail("commits")
        assert_project_ref(project_ref)
        await maybe_delay()

        commits = list(dataset.commits_by_branch.get(ref_name, []))
        since_dt = parse_iso_datetime(since)
        if since_dt is not None:
            commits = [
                item
                for item in commits
                if (parse_iso_datetime(item.get("committed_date")) or since_dt) >= since_dt
            ]

        commits.sort(
            key=lambda item: parse_iso_datetime(item.get("committed_date")) or datetime.min,
            reverse=True,
        )
        start = (page - 1) * per_page
        end = start + per_page
        _ = request  # keeps signature explicit for future request-aware behavior
        return commits[start:end]

    @app.get("/api/v4/projects/{project_ref:path}")
    async def get_project(project_ref: str) -> dict:
        maybe_fail("project")
        assert_project_ref(project_ref)
        await maybe_delay()
        return dataset.project

    return app
