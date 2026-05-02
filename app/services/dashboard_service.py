from __future__ import annotations

from datetime import timedelta

from app.models.schemas import DashboardCard
from app.services.job_runner import scan_readiness
from app.services import jobs_service
from app.services.audit_service import recent_events
from app.services.inventory_service import counts_by_vendor
from app.utils.helpers import humanize_timestamp, parse_timestamp, utcnow


def build_dashboard(app) -> dict:
    counts = counts_by_vendor()
    cards = []
    for vendor in ("cambium", "ubiquiti"):
        latest = jobs_service.latest_successful_run(vendor)
        finished_at = latest["finished_at"] if latest else None
        parsed = parse_timestamp(finished_at)
        stale = parsed is None or utcnow() - parsed > timedelta(minutes=app.config["STALE_SCAN_THRESHOLD_MINUTES"])
        meta = latest.get("meta", {}) if latest else {}
        detail = f"Last success: {humanize_timestamp(finished_at)} | Last import: {meta.get('processed', 0)} rows"
        if meta.get("failed_targets"):
            detail += f" | Target failures: {meta['failed_targets']}"
        cards.append(
            DashboardCard(
                label=f"{vendor.title()} inventory",
                value=str(counts.get(vendor, 0)),
                status="stale" if stale else "healthy",
                detail=detail,
            )
        )

    return {
        "cards": cards,
        "recent_jobs": jobs_service.list_recent_jobs(limit=8),
        "recent_audit_events": recent_events(limit=8),
        "scan_controls": {
            "cambium": scan_readiness(app, "cambium"),
            "ubiquiti": scan_readiness(app, "ubiquiti"),
        },
    }
