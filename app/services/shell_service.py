from __future__ import annotations

from datetime import timedelta

from app.services.audit_service import recent_events
from app.services.jobs_service import is_scan_running, latest_successful_run
from app.utils.helpers import humanize_timestamp, parse_timestamp, utcnow


def build_shell_context(app, current_user, endpoint: str | None) -> dict:
    nav = [
        {"label": "Monitoring", "endpoint": "monitoring.index", "match_prefix": "/monitoring", "match_mode": "path"},
        {"label": "Cambium Inventory", "endpoint": "inventory.view_inventory", "route_args": {"vendor": "cambium"}, "match_prefix": "/inventory/cambium", "match_mode": "path"},
        {"label": "Ubiquiti Inventory", "endpoint": "inventory.view_inventory", "route_args": {"vendor": "ubiquiti"}, "match_prefix": "/inventory/ubiquiti", "match_mode": "path"},
        {"label": "Switch Inspection", "endpoint": "switches.inspect", "route_args": {"inventory_type": "ultra"}, "match_mode": "endpoint"},
    ]
    if current_user and current_user["role"] in {"operator", "admin"}:
        nav.insert(1, {"label": "Dashboard", "endpoint": "dashboard.index", "match_mode": "endpoint"})
        nav.append({"label": "Port Change Workflow", "endpoint": "switches.change", "match_prefix": "/switches/change", "match_mode": "path"})
        nav.append({"label": "Scan Schedule", "endpoint": "jobs.schedule", "match_prefix": "/jobs/schedule", "match_mode": "path"})
        nav.extend(
            [
                {"label": "Jobs", "endpoint": "jobs.list_jobs", "match_mode": "endpoint"},
                {"label": "Audit Log", "endpoint": "audit.index", "match_mode": "endpoint"},
                {"label": "Settings", "endpoint": "settings.index", "match_mode": "endpoint"},
            ]
        )
    if current_user and current_user["role"] == "admin":
        nav.append({"label": "Switch Inventory Admin", "endpoint": "admin.switches", "match_mode": "endpoint"})
        nav.append({"label": "User Admin", "endpoint": "admin.users", "match_mode": "endpoint"})

    vendors = [_scan_status(app, "cambium"), _scan_status(app, "ubiquiti")]
    stale_vendors = [vendor["label"] for vendor in vendors if vendor["tone"] == "danger"]
    banner = None
    if stale_vendors:
        banner = {
            "tone": "danger",
            "title": "Stale inventory detected",
            "message": f"{', '.join(stale_vendors)} data needs operator attention or a fresh scan.",
        }

    return {
        "shell_nav": nav,
        "shell_status": vendors,
        "shell_banner": banner,
        "shell_recent_events": recent_events(limit=5),
        "active_endpoint": endpoint or "",
    }


def _scan_status(app, vendor: str) -> dict:
    latest = latest_successful_run(vendor)
    finished_at = latest["finished_at"] if latest else None
    parsed = parse_timestamp(finished_at)
    stale_after = timedelta(minutes=app.config["STALE_SCAN_THRESHOLD_MINUTES"])
    is_stale = parsed is None or utcnow() - parsed > stale_after
    running = is_scan_running(vendor)

    if running:
        tone = "info"
        meta = "Scan running"
    elif is_stale:
        tone = "danger"
        meta = "Refresh needed"
    else:
        tone = "success"
        meta = "Current"

    return {
        "label": vendor.title(),
        "value": humanize_timestamp(finished_at),
        "meta": meta,
        "tone": tone,
    }
