from __future__ import annotations

import asyncio
import logging
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings as app_config
from app.llm import LLMClient
from app.models.commit import Commit
from app.models.contributor import Contributor
from app.models.daily_report import DailyReport
from app.schemas.report import (
    DailyReportGenerationResponse,
    DailyReportItem,
    DailyReportListResponse,
    ReportDateItem,
    ReportDateListResponse,
)
from app.services.settings_service import get_or_create_settings

logger = logging.getLogger(__name__)


@dataclass
class CommitContext:
    commit: Commit
    contributor: Contributor | None


def ensure_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def get_yesterday_window(timezone_name: str) -> tuple[date, datetime, datetime]:
    tz = ZoneInfo(timezone_name)
    now_local = datetime.now(tz)
    report_date = now_local.date() - timedelta(days=1)
    _, start_utc, end_utc = get_report_window(report_date, timezone_name)
    return report_date, start_utc, end_utc


def get_report_window(report_date: date, timezone_name: str) -> tuple[date, datetime, datetime]:
    tz = ZoneInfo(timezone_name)
    start_local = datetime.combine(report_date, time.min, tzinfo=tz)
    end_local = datetime.combine(report_date, time.max, tzinfo=tz)
    return report_date, start_local.astimezone(UTC), end_local.astimezone(UTC)


def to_local_report_date(value: datetime | None, timezone_name: str) -> date | None:
    normalized = ensure_utc(value)
    if normalized is None:
        return None
    return normalized.astimezone(ZoneInfo(timezone_name)).date()


def normalize_key(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip().lower()
    return stripped or None


def format_person_label(contributor: Contributor | None, fallback_name: str | None) -> str:
    base_name = contributor.name if contributor else (fallback_name or "未知成员")
    if contributor and contributor.component:
        return f"{base_name}（{contributor.component}）"
    return base_name


def format_commit_time(value: datetime | None, timezone_name: str) -> str:
    normalized = ensure_utc(value)
    if normalized is None:
        return "未知时间"
    return normalized.astimezone(ZoneInfo(timezone_name)).strftime("%Y-%m-%d %H:%M:%S")


def build_project_fact_sheet(report_date: date, contexts: list[CommitContext], timezone_name: str) -> str:
    branch_groups: dict[str, list[CommitContext]] = defaultdict(list)
    person_counts: Counter[str] = Counter()
    component_groups: dict[str, list[CommitContext]] = defaultdict(list)
    unknown_people: set[str] = set()

    for ctx in contexts:
        branch_groups[ctx.commit.branch_name].append(ctx)
        person_counts[format_person_label(ctx.contributor, ctx.commit.author_name)] += 1
        component = ctx.contributor.component if ctx.contributor and ctx.contributor.component else "未映射组件"
        component_groups[component].append(ctx)
        if ctx.contributor is None and ctx.commit.author_name:
            unknown_people.add(ctx.commit.author_name)

    lines = [
        f"日报日期：{report_date.isoformat()}",
        f"范围：{report_date.isoformat()} 00:00:00 到 23:59:59（{timezone_name}）",
        f"提交总数：{len(contexts)}",
        f"涉及分支数：{len(branch_groups)}",
        f"活跃开发者数：{len(person_counts)}",
    ]

    lines.append("活跃开发者统计：")
    for name, count in person_counts.most_common():
        lines.append(f"- {name}：{count} 条 commit")

    lines.append("分支事实：")
    for branch_name in sorted(branch_groups):
        branch_contexts = sorted(
            branch_groups[branch_name],
            key=lambda item: ensure_utc(item.commit.committed_at) or datetime.min.replace(tzinfo=UTC),
            reverse=True,
        )
        people = sorted({format_person_label(ctx.contributor, ctx.commit.author_name) for ctx in branch_contexts}) or ["未知成员"]
        lines.append(f"- 分支 {branch_name}：{len(branch_contexts)} 条 commit；开发者：{', '.join(people)}")
        for item in branch_contexts:
            component = item.contributor.component if item.contributor and item.contributor.component else "未映射组件"
            title = item.commit.title or item.commit.message or "(无标题)"
            lines.append(
                f"  - {format_commit_time(item.commit.committed_at, timezone_name)} | "
                f"{format_person_label(item.contributor, item.commit.author_name)} | {component} | {title}"
            )

    lines.append("组件统计：")
    for component_name in sorted(component_groups):
        component_contexts = component_groups[component_name]
        titles = [item.commit.title or item.commit.message or "(无标题)" for item in component_contexts]
        lines.append(f"- {component_name}：{len(component_contexts)} 条 commit；事项：{'；'.join(titles)}")

    lines.append("未匹配成员：")
    if unknown_people:
        lines.append(f"- {', '.join(sorted(unknown_people))}")
    else:
        lines.append("- 无")

    return "\n".join(lines)


def build_branch_fact_sheet(
    report_date: date,
    branch_name: str,
    contexts: list[CommitContext],
    timezone_name: str,
) -> str:
    person_counts: Counter[str] = Counter()
    components: set[str] = set()
    for ctx in contexts:
        person_counts[format_person_label(ctx.contributor, ctx.commit.author_name)] += 1
        if ctx.contributor and ctx.contributor.component:
            components.add(ctx.contributor.component)

    ordered_contexts = sorted(
        contexts,
        key=lambda item: ensure_utc(item.commit.committed_at) or datetime.min.replace(tzinfo=UTC),
        reverse=True,
    )

    lines = [
        f"日报日期：{report_date.isoformat()}",
        f"分支：{branch_name}",
        f"范围：{report_date.isoformat()} 00:00:00 到 23:59:59（{timezone_name}）",
        f"提交总数：{len(contexts)}",
        f"活跃开发者数：{len(person_counts)}",
    ]

    lines.append("开发者统计：")
    for name, count in person_counts.most_common():
        lines.append(f"- {name}：{count} 条 commit")

    lines.append("提交事实：")
    for ctx in ordered_contexts:
        author_label = format_person_label(ctx.contributor, ctx.commit.author_name)
        component = ctx.contributor.component if ctx.contributor and ctx.contributor.component else "未映射组件"
        title = ctx.commit.title or ctx.commit.message or "(无标题)"
        lines.append(f"- {format_commit_time(ctx.commit.committed_at, timezone_name)} | {author_label} | {component} | {title}")

    lines.append("组件范围：")
    if components:
        lines.append(f"- 涉及组件：{', '.join(sorted(components))}")
    else:
        lines.append("- 当前分支提交尚未匹配到明确组件。")

    return "\n".join(lines)


async def generate_project_report_content(
    llm_client: LLMClient,
    report_date: date,
    contexts: list[CommitContext],
    timezone_name: str,
) -> str:
    fact_sheet = build_project_fact_sheet(report_date, contexts, timezone_name)
    system_prompt = (
        "你是技术项目经理助手。"
        "你的任务是根据提供的 Git 提交事实，生成中文项目日报。"
        "只能基于给定事实总结，不得虚构。"
        "输出纯文本，不要代码块，不要表格，不要使用 markdown 标题符号。"
        "表达要简洁、专业、面向项目经理。"
    )
    user_prompt = (
        f"请基于下面事实生成 1 份项目整体日报，日期是 {report_date.isoformat()}。\n"
        "必须严格使用以下结构，并保持每个小节下面使用 '-' 开头的项目符号：\n"
        "项目整体日报 | 日期\n"
        "整体概况\n"
        "- ...\n"
        "活跃开发者\n"
        "- ...\n"
        "分支进展\n"
        "- ...\n"
        "组件进展\n"
        "- ...\n"
        "关注事项\n"
        "- ...\n\n"
        "注意：\n"
        f"- 整体概况要先给出 {report_date.isoformat()} 当天整体性的项目进度总结，而不是简单罗列 commit 数。\n"
        f"- 分支进展要归纳每个分支在 {report_date.isoformat()} 这一天推进了什么。\n"
        "- 组件进展要结合组件信息归纳影响范围。\n"
        "- 如果有成员未匹配，要写入关注事项。\n"
        f"- 如果没有 commit，要明确写出 {report_date.isoformat()} 当天没有新增代码进展。\n\n"
        f"事实如下：\n{fact_sheet}"
    )
    return await llm_client.generate_text(system_prompt=system_prompt, user_prompt=user_prompt)


async def generate_branch_report_content(
    llm_client: LLMClient,
    report_date: date,
    branch_name: str,
    contexts: list[CommitContext],
    timezone_name: str,
) -> str:
    fact_sheet = build_branch_fact_sheet(report_date, branch_name, contexts, timezone_name)
    system_prompt = (
        "你是技术项目经理助手。"
        "你的任务是根据提供的 Git 提交事实，生成中文分支日报。"
        "只能基于给定事实总结，不得虚构。"
        "输出纯文本，不要代码块，不要表格，不要使用 markdown 标题符号。"
        "表达要简洁、专业、面向项目经理。"
    )
    user_prompt = (
        f"请基于下面事实生成 1 份分支日报，分支是 {branch_name}，日期是 {report_date.isoformat()}。\n"
        "必须严格使用以下结构，并保持每个小节下面使用 '-' 开头的项目符号：\n"
        "分支日报 | 分支名 | 日期\n"
        "整体概况\n"
        "- ...\n"
        "开发者分布\n"
        "- ...\n"
        "主要进展\n"
        "- ...\n"
        "组件范围\n"
        "- ...\n\n"
        "注意：\n"
        f"- 主要进展要总结这个分支在 {report_date.isoformat()} 当天推进了什么，而不是简单重复所有 commit 标题。\n"
        "- 组件范围要基于已有成员映射，不得虚构组件。\n"
        "- 只根据给定事实输出。\n\n"
        f"事实如下：\n{fact_sheet}"
    )
    return await llm_client.generate_text(system_prompt=system_prompt, user_prompt=user_prompt)


async def list_report_dates(session: AsyncSession) -> ReportDateListResponse:
    settings = await get_or_create_settings(session)
    commit_result = await session.execute(
        select(Commit.committed_at).where(Commit.committed_at.is_not(None)).order_by(Commit.committed_at.desc())
    )
    commit_counts: Counter[date] = Counter()
    for committed_at in commit_result.scalars().all():
        local_date = to_local_report_date(committed_at, settings.timezone)
        if local_date is not None:
            commit_counts[local_date] += 1

    report_result = await session.execute(select(DailyReport.report_date).distinct())
    generated_dates = {value for value in report_result.scalars().all() if value is not None}
    ordered_dates = sorted(commit_counts.keys(), reverse=True)
    logger.info(
        "list_report_dates timezone=%s available_dates=%s",
        settings.timezone,
        [report_date.isoformat() for report_date in ordered_dates],
    )
    return ReportDateListResponse(
        selected_date=ordered_dates[0] if ordered_dates else None,
        items=[
            ReportDateItem(
                report_date=report_date,
                commit_count=commit_counts[report_date],
                has_reports=report_date in generated_dates,
            )
            for report_date in ordered_dates
        ],
    )


async def list_project_reports(
    session: AsyncSession,
    report_date: date | None = None,
) -> DailyReportListResponse:
    stmt = select(DailyReport).where(DailyReport.report_type == "project")
    if report_date is not None:
        stmt = stmt.where(DailyReport.report_date == report_date)
    stmt = stmt.order_by(DailyReport.report_date.desc(), DailyReport.created_at.desc())
    result = await session.execute(stmt)
    rows = list(result.scalars().all())
    return DailyReportListResponse(
        report_date=report_date,
        items=[DailyReportItem.model_validate(row) for row in rows],
        branch_names=[],
    )


async def list_branch_reports(
    session: AsyncSession,
    branch: str | None = None,
    report_date: date | None = None,
) -> DailyReportListResponse:
    stmt = select(DailyReport).where(DailyReport.report_type == "branch")
    if branch:
        stmt = stmt.where(DailyReport.branch_name == branch)
    if report_date is not None:
        stmt = stmt.where(DailyReport.report_date == report_date)
    stmt = stmt.order_by(DailyReport.branch_name.asc(), DailyReport.report_date.desc(), DailyReport.created_at.desc())

    result = await session.execute(stmt)
    rows = list(result.scalars().all())
    branch_names = sorted({row.branch_name for row in rows if row.branch_name})
    return DailyReportListResponse(
        report_date=report_date,
        items=[DailyReportItem.model_validate(row) for row in rows],
        branch_names=branch_names,
    )


async def generate_daily_reports(
    session: AsyncSession,
    report_date: date | None = None,
) -> DailyReportGenerationResponse:
    settings = await get_or_create_settings(session)
    if report_date is None:
        report_date, start_utc, end_utc = get_yesterday_window(settings.timezone)
    else:
        report_date, start_utc, end_utc = get_report_window(report_date, settings.timezone)

    commits_result = await session.execute(
        select(Commit)
        .where(Commit.committed_at >= start_utc, Commit.committed_at <= end_utc)
        .order_by(Commit.committed_at.desc().nullslast(), Commit.id.desc())
    )
    commits = list(commits_result.scalars().all())
    logger.info(
        "generate_daily_reports_started report_date=%s timezone=%s commit_count=%s",
        report_date.isoformat(),
        settings.timezone,
        len(commits),
    )

    contributors_result = await session.execute(select(Contributor).where(Contributor.is_active.is_(True)))
    contributors = list(contributors_result.scalars().all())
    contributors_by_name = {normalize_key(item.name): item for item in contributors if normalize_key(item.name)}
    contributors_by_username = {
        normalize_key(item.gitlab_username): item for item in contributors if normalize_key(item.gitlab_username)
    }

    contexts: list[CommitContext] = []
    for commit in commits:
        author_key = normalize_key(commit.author_name)
        contributor = None
        if author_key:
            contributor = contributors_by_name.get(author_key) or contributors_by_username.get(author_key)
        contexts.append(CommitContext(commit=commit, contributor=contributor))

    await session.execute(delete(DailyReport).where(DailyReport.report_date == report_date))
    logger.info(
        "generate_daily_reports_context_ready report_date=%s active_contributors=%s matched_contexts=%s",
        report_date.isoformat(),
        len(contributors),
        len(contexts),
    )

    grouped_by_branch: dict[str, list[CommitContext]] = defaultdict(list)
    for ctx in contexts:
        grouped_by_branch[ctx.commit.branch_name].append(ctx)
    logger.info(
        "generate_daily_reports_branch_groups report_date=%s branches=%s",
        report_date.isoformat(),
        {branch_name: len(items) for branch_name, items in grouped_by_branch.items()},
    )

    async with LLMClient.from_app_config(app_config) as llm_client:
        logger.info(
            "generate_daily_reports_llm_started provider=%s model=%s report_date=%s",
            llm_client.config.provider,
            llm_client.model,
            report_date.isoformat(),
        )
        project_content = await generate_project_report_content(
            llm_client=llm_client,
            report_date=report_date,
            contexts=contexts,
            timezone_name=settings.timezone,
        )
        branch_contents = await asyncio.gather(
            *[
                generate_branch_report_content(
                    llm_client=llm_client,
                    report_date=report_date,
                    branch_name=branch_name,
                    contexts=grouped_by_branch[branch_name],
                    timezone_name=settings.timezone,
                )
                for branch_name in sorted(grouped_by_branch)
            ]
        )
        logger.info(
            "generate_daily_reports_llm_finished report_date=%s branch_report_count=%s",
            report_date.isoformat(),
            len(branch_contents),
        )

    project_report = DailyReport(
        report_date=report_date,
        report_type="project",
        branch_name=None,
        content=project_content,
        status="draft",
    )
    session.add(project_report)

    branch_reports: list[DailyReport] = []
    for branch_name, content in zip(sorted(grouped_by_branch), branch_contents):
        branch_report = DailyReport(
            report_date=report_date,
            report_type="branch",
            branch_name=branch_name,
            content=content,
            status="draft",
        )
        session.add(branch_report)
        branch_reports.append(branch_report)

    await session.commit()
    await session.refresh(project_report)
    for item in branch_reports:
        await session.refresh(item)

    logger.info(
        "generate_daily_reports_finished report_date=%s project_report_id=%s branch_report_ids=%s",
        report_date.isoformat(),
        project_report.id,
        [item.id for item in branch_reports],
    )
    return DailyReportGenerationResponse(
        report_date=report_date,
        commit_count=len(contexts),
        branch_count=len(branch_reports),
        project_report=DailyReportItem.model_validate(project_report),
        branch_reports=[DailyReportItem.model_validate(item) for item in branch_reports],
    )
