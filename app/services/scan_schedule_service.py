from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.db import get_db
from app.services import jobs_service
from app.utils.helpers import local_now, parse_timestamp, utcnow_iso
from app.utils.validation import normalize_vendor


SUPPORTED_VENDORS = ("cambium", "ubiquiti")


def list_schedules(now: datetime | None = None) -> list[dict]:
    current = now or local_now()
    rows = get_db().execute(
        """
        SELECT vendor, enabled, daily_time, updated_at
        FROM scan_schedules
        """
    ).fetchall()
    raw = {row["vendor"]: dict(row) for row in rows}
    schedules = []
    for vendor in SUPPORTED_VENDORS:
        schedule = raw.get(vendor) or {
            "vendor": vendor,
            "enabled": 0,
            "daily_time": "",
            "updated_at": None,
        }
        schedules.append(_enrich_schedule(schedule, current))
    return schedules


def get_schedule(vendor: str, now: datetime | None = None) -> dict:
    normalized = normalize_vendor(vendor)
    schedule = next((item for item in list_schedules(now=now) if item["vendor"] == normalized), None)
    if schedule is None:
        raise ValueError("Unsupported vendor.")
    return schedule


def save_schedule(vendor: str, enabled: bool, daily_time: str) -> dict:
    normalized = normalize_vendor(vendor)
    db = get_db()
    db.execute(
        """
        INSERT INTO scan_schedules (vendor, enabled, daily_time, updated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(vendor) DO UPDATE SET
            enabled = excluded.enabled,
            daily_time = excluded.daily_time,
            updated_at = excluded.updated_at
        """,
        (normalized, 1 if enabled else 0, daily_time or "", utcnow_iso()),
    )
    db.commit()
    return get_schedule(normalized)


def should_enqueue_scheduled_scan(vendor: str, now: datetime | None = None) -> bool:
    schedule = get_schedule(vendor, now=now)
    return _schedule_due(schedule, now or local_now())


def _schedule_due(schedule: dict, now: datetime) -> bool:
    if not schedule["enabled"] or not schedule["daily_time"]:
        return False

    scheduled_at_local = _scheduled_at_local(now, schedule["daily_time"])
    if now < scheduled_at_local:
        return False

    scheduled_at_utc = scheduled_at_local.astimezone(timezone.utc)
    return not jobs_service.has_scan_job_since(schedule["vendor"], scheduled_at_utc)


def _scheduled_at_local(current: datetime, daily_time: str) -> datetime:
    hour, minute = [int(part) for part in daily_time.split(":", 1)]
    return current.replace(hour=hour, minute=minute, second=0, microsecond=0)


def _enrich_schedule(schedule: dict, now: datetime) -> dict:
    enabled = bool(schedule.get("enabled"))
    daily_time = schedule.get("daily_time") or ""
    updated_at = schedule.get("updated_at")
    scheduled_today = _scheduled_at_local(now, daily_time) if daily_time else None
    last_job = jobs_service.latest_scan_job(schedule["vendor"])
    last_job_at = None
    last_job_after_schedule = False
    if last_job:
        last_job_at = parse_timestamp(last_job.get("created_at"))
        if scheduled_today and last_job_at:
            last_job_after_schedule = last_job_at >= scheduled_today.astimezone(timezone.utc)

    next_run_at = None
    if enabled and daily_time and scheduled_today:
        target = scheduled_today
        if now >= scheduled_today and last_job_after_schedule:
            target = scheduled_today + timedelta(days=1)
        elif now > scheduled_today and not last_job_after_schedule:
            target = now
        next_run_at = target.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")

    return {
        "vendor": schedule["vendor"],
        "enabled": enabled,
        "daily_time": daily_time,
        "updated_at": updated_at,
        "last_job": last_job,
        "next_run_at": next_run_at,
        "due_now": _schedule_due({"vendor": schedule["vendor"], "enabled": enabled, "daily_time": daily_time}, now),
    }
