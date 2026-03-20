from __future__ import annotations

import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from httpx import HTTPError

from app.db.session import async_session_maker
from app.llm import LLMConfigError, LLMRequestError
from app.services.feishu_client import FeishuConfigError
from app.services.feishu_service import sync_feishu_contributors
from app.services.gitlab_client import GitLabConfigError
from app.services.report_service import generate_daily_reports, send_daily_reports_to_feishu
from app.services.settings_service import get_or_create_settings
from app.services.sync_service import sync_branches, sync_commits_with_mode


logger = logging.getLogger(__name__)

JOB_SYNC_COMMITS = "sync_commits"
JOB_SYNC_CONTRIBUTORS = "sync_feishu_contributors"
JOB_GENERATE_AND_SEND_REPORTS = "generate_and_send_daily_reports"

_scheduler: AsyncIOScheduler | None = None
_scheduler_lock = asyncio.Lock()


async def start_scheduler() -> None:
    global _scheduler

    async with _scheduler_lock:
        if _scheduler is None:
            _scheduler = AsyncIOScheduler()
            _scheduler.start()
            logger.info("scheduler_started")

        await _reload_jobs_locked()


async def reload_scheduler() -> None:
    async with _scheduler_lock:
        await _reload_jobs_locked()


async def stop_scheduler() -> None:
    global _scheduler

    async with _scheduler_lock:
        if _scheduler is None:
            return

        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("scheduler_stopped")


async def _reload_jobs_locked() -> None:
    if _scheduler is None:
        return

    async with async_session_maker() as session:
        settings = await get_or_create_settings(session)

    timezone_name = settings.timezone or "Asia/Shanghai"
    sync_interval_minutes = max(1, int(settings.sync_interval_minutes or 15))

    _scheduler.add_job(
        scheduled_sync_commits_job,
        trigger=IntervalTrigger(minutes=sync_interval_minutes, timezone=timezone_name),
        id=JOB_SYNC_COMMITS,
        replace_existing=True,
        coalesce=True,
        max_instances=1,
        misfire_grace_time=300,
    )
    _scheduler.add_job(
        scheduled_sync_feishu_contributors_job,
        trigger=CronTrigger(hour=23, minute=50, second=0, timezone=timezone_name),
        id=JOB_SYNC_CONTRIBUTORS,
        replace_existing=True,
        coalesce=True,
        max_instances=1,
        misfire_grace_time=1800,
    )
    _scheduler.add_job(
        scheduled_generate_and_send_reports_job,
        trigger=CronTrigger(hour=0, minute=0, second=0, timezone=timezone_name),
        id=JOB_GENERATE_AND_SEND_REPORTS,
        replace_existing=True,
        coalesce=True,
        max_instances=1,
        misfire_grace_time=1800,
    )

    for job_id in (JOB_SYNC_COMMITS, JOB_SYNC_CONTRIBUTORS, JOB_GENERATE_AND_SEND_REPORTS):
        job = _scheduler.get_job(job_id)
        logger.info(
            "scheduler_job_registered job_id=%s next_run_time=%s timezone=%s",
            job_id,
            job.next_run_time.isoformat() if job and job.next_run_time else "-",
            timezone_name,
        )


async def scheduled_sync_commits_job() -> None:
    logger.info("scheduler_sync_commits_started")
    async with async_session_maker() as session:
        try:
            branch_result = await sync_branches(session)
            commit_result = await sync_commits_with_mode(session, full_sync=False)
            logger.info(
                "scheduler_sync_commits_finished branches=%s commits=%s synced_at=%s",
                branch_result.synced_count,
                commit_result.commit_count,
                commit_result.synced_at.isoformat(),
            )
        except GitLabConfigError as exc:
            logger.warning("scheduler_sync_commits_skipped reason=%s", exc)
        except HTTPError:
            logger.exception("scheduler_sync_commits_failed transport_error")
        except Exception:
            logger.exception("scheduler_sync_commits_failed unexpected_error")


async def scheduled_sync_feishu_contributors_job() -> None:
    logger.info("scheduler_sync_feishu_contributors_started")
    async with async_session_maker() as session:
        try:
            result = await sync_feishu_contributors(session)
            logger.info(
                "scheduler_sync_feishu_contributors_finished synced=%s active=%s",
                result.synced_count,
                result.active_count,
            )
        except FeishuConfigError as exc:
            logger.warning("scheduler_sync_feishu_contributors_skipped reason=%s", exc)
        except HTTPError:
            logger.exception("scheduler_sync_feishu_contributors_failed transport_error")
        except Exception:
            logger.exception("scheduler_sync_feishu_contributors_failed unexpected_error")


async def scheduled_generate_and_send_reports_job() -> None:
    logger.info("scheduler_generate_and_send_reports_started")
    async with async_session_maker() as session:
        try:
            generated = await generate_daily_reports(session)
            sent = await send_daily_reports_to_feishu(session, report_date=generated.report_date)
            logger.info(
                "scheduler_generate_and_send_reports_finished report_date=%s commits=%s reports=%s messages=%s",
                generated.report_date.isoformat(),
                generated.commit_count,
                sent.report_count,
                sent.message_count,
            )
        except (LLMConfigError, FeishuConfigError, GitLabConfigError) as exc:
            logger.warning("scheduler_generate_and_send_reports_skipped reason=%s", exc)
        except (LLMRequestError, HTTPError):
            logger.exception("scheduler_generate_and_send_reports_failed upstream_error")
        except Exception:
            logger.exception("scheduler_generate_and_send_reports_failed unexpected_error")
