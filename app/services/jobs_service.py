from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from app.db import get_db
from app.utils.helpers import parse_timestamp, utcnow, utcnow_iso


def create_job(job_type: str, vendor: str | None, trigger_source: str, requested_by: int | None) -> int:
    db = get_db()
    db.execute(
        """
        INSERT INTO jobs (job_type, vendor, trigger_source, status, requested_by, message, meta_json, created_at)
        VALUES (?, ?, ?, 'queued', ?, '', '{}', ?)
        """,
        (job_type, vendor, trigger_source, requested_by, utcnow_iso()),
    )
    db.commit()
    return db.execute("SELECT last_insert_rowid()").fetchone()[0]


def mark_job_running(job_id: int) -> bool:
    db = get_db()
    cursor = db.execute(
        "UPDATE jobs SET status = 'running', started_at = ? WHERE id = ? AND status = 'queued'",
        (utcnow_iso(), job_id),
    )
    db.commit()
    return cursor.rowcount > 0


def mark_job_finished(job_id: int, status: str, message: str = "", meta: dict | None = None) -> bool:
    db = get_db()
    cursor = db.execute(
        """
        UPDATE jobs
        SET status = ?, message = ?, meta_json = ?, finished_at = ?
        WHERE id = ? AND status = 'running'
        """,
        (status, message, json.dumps(meta or {}, sort_keys=True), utcnow_iso(), job_id),
    )
    db.commit()
    return cursor.rowcount > 0


def get_job(job_id: int) -> dict | None:
    row = get_db().execute(
        """
        SELECT id, job_type, vendor, trigger_source, status, requested_by,
               message, meta_json, created_at, started_at, finished_at
        FROM jobs
        WHERE id = ?
        """,
        (job_id,),
    ).fetchone()
    return _enrich_job(dict(row)) if row else None


def list_active_scan_jobs(vendor: str) -> list[dict]:
    rows = get_db().execute(
        """
        SELECT id, job_type, vendor, trigger_source, status, requested_by,
               message, meta_json, created_at, started_at, finished_at
        FROM jobs
        WHERE job_type = 'scan' AND vendor = ? AND status IN ('queued', 'running')
        ORDER BY id DESC
        """,
        (vendor,),
    ).fetchall()
    return [_enrich_job(dict(row)) for row in rows]


def cancel_scan_jobs(
    vendor: str,
    message: str,
    meta: dict | None = None,
    exclude_job_id: int | None = None,
) -> list[int]:
    active_jobs = list_active_scan_jobs(vendor)
    canceled_ids = []
    for job in active_jobs:
        if exclude_job_id and job["id"] == exclude_job_id:
            continue
        cancel_job(job["id"], message=message, meta=meta)
        canceled_ids.append(job["id"])
    return canceled_ids


def cancel_job(job_id: int, message: str, meta: dict | None = None) -> bool:
    db = get_db()
    cursor = db.execute(
        """
        UPDATE jobs
        SET status = 'canceled', message = ?, meta_json = ?
        WHERE id = ? AND status IN ('queued', 'running')
        """,
        (message, json.dumps(meta or {}, sort_keys=True), job_id),
    )
    db.commit()
    return cursor.rowcount > 0


def finalize_canceled_job(job_id: int, message: str | None = None) -> bool:
    db = get_db()
    if message is None:
        cursor = db.execute(
            "UPDATE jobs SET finished_at = ? WHERE id = ? AND status = 'canceled' AND finished_at IS NULL",
            (utcnow_iso(), job_id),
        )
    else:
        cursor = db.execute(
            """
            UPDATE jobs
            SET message = ?, finished_at = ?
            WHERE id = ? AND status = 'canceled' AND finished_at IS NULL
            """,
            (message, utcnow_iso(), job_id),
        )
    db.commit()
    return cursor.rowcount > 0


def is_job_active(job_id: int) -> bool:
    row = get_db().execute(
        """
        SELECT 1
        FROM jobs
        WHERE id = ? AND status IN ('queued', 'running')
        LIMIT 1
        """,
        (job_id,),
    ).fetchone()
    return row is not None


def is_job_canceled(job_id: int) -> bool:
    row = get_db().execute(
        """
        SELECT 1
        FROM jobs
        WHERE id = ? AND status = 'canceled'
        LIMIT 1
        """,
        (job_id,),
    ).fetchone()
    return row is not None


def list_recent_jobs(limit: int | None = 20, offset: int = 0) -> list[dict]:
    sql = """
        SELECT id, job_type, vendor, trigger_source, status, requested_by,
               message, meta_json, created_at, started_at, finished_at
        FROM jobs
        ORDER BY id DESC
    """
    params: list[int] = []
    if limit is not None:
        sql += " LIMIT ? OFFSET ?"
        params.extend([limit, max(0, offset)])
    rows = get_db().execute(sql, tuple(params)).fetchall()
    return [_enrich_job(dict(row)) for row in rows]


def latest_successful_run(vendor: str) -> dict | None:
    row = get_db().execute(
        """
        SELECT id, vendor, finished_at, created_at, meta_json
        FROM jobs
        WHERE job_type = 'scan' AND vendor = ? AND status = 'success'
        ORDER BY id DESC
        LIMIT 1
        """,
        (vendor,),
    ).fetchone()
    return _enrich_job(dict(row)) if row else None


def latest_scan_job(vendor: str) -> dict | None:
    row = get_db().execute(
        """
        SELECT id, job_type, vendor, trigger_source, status, requested_by,
               message, meta_json, created_at, started_at, finished_at
        FROM jobs
        WHERE job_type = 'scan' AND vendor = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (vendor,),
    ).fetchone()
    return _enrich_job(dict(row)) if row else None


def is_scan_running(vendor: str) -> bool:
    row = get_db().execute(
        """
        SELECT 1
        FROM jobs
        WHERE job_type = 'scan' AND vendor = ? AND status IN ('queued', 'running')
        LIMIT 1
        """,
        (vendor,),
    ).fetchone()
    return row is not None


def has_scan_job_since(vendor: str, since: datetime) -> bool:
    row = get_db().execute(
        """
        SELECT 1
        FROM jobs
        WHERE job_type = 'scan' AND vendor = ? AND created_at >= ?
        LIMIT 1
        """,
        (vendor, since.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")),
    ).fetchone()
    return row is not None


def should_schedule(vendor: str, interval_minutes: int) -> bool:
    if is_scan_running(vendor):
        return False
    latest = latest_successful_run(vendor)
    if latest is None:
        return True
    finished_at = parse_timestamp(latest["finished_at"] or latest["created_at"])
    if finished_at is None:
        return True
    return utcnow() - finished_at >= timedelta(minutes=interval_minutes)


def summarize_jobs(stale_threshold_minutes: int) -> dict:
    jobs = list_recent_jobs(limit=50)
    queued = sum(1 for job in jobs if job["status"] == "queued")
    running = sum(1 for job in jobs if job["status"] == "running")
    failed = sum(1 for job in jobs if job["status"] == "failed")

    vendors = []
    for vendor in ("cambium", "ubiquiti"):
        latest = latest_successful_run(vendor)
        finished_at = latest["finished_at"] if latest else latest["created_at"] if latest else None
        parsed = parse_timestamp(finished_at)
        is_stale = parsed is None or utcnow() - parsed > timedelta(minutes=stale_threshold_minutes)
        meta = latest.get("meta", {}) if latest else {}
        vendors.append(
            {
                "vendor": vendor,
                "last_success": finished_at,
                "is_stale": is_stale,
                "processed": meta.get("processed", 0),
                "failed_targets": meta.get("failed_targets", 0),
            }
        )

    return {
        "total": len(jobs),
        "queued": queued,
        "running": running,
        "failed": failed,
        "vendors": vendors,
    }


def _enrich_job(job: dict) -> dict:
    meta = _load_meta(job.get("meta_json"))
    job["meta"] = meta
    job["duration_seconds"] = _duration_seconds(job.get("started_at"), job.get("finished_at"))
    job["processed"] = meta.get("processed")
    job["failed_targets"] = meta.get("failed_targets", 0)
    job["successful_targets"] = meta.get("successful_targets")
    job["failure_samples"] = meta.get("failure_samples", [])
    return job


def _load_meta(raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def _duration_seconds(started_at: str | None, finished_at: str | None) -> int | None:
    started = parse_timestamp(started_at)
    finished = parse_timestamp(finished_at)
    if started is None or finished is None:
        return None
    return max(0, int((finished - started).total_seconds()))
