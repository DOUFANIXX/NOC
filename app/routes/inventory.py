from __future__ import annotations

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for

from app.services import audit_service
from app.services.job_runner import scan_readiness
from app.services.jobs_service import latest_successful_run
from app.services.inventory_service import distinct_values, list_devices
from app.utils.auth import login_required, role_required
from app.utils.helpers import paginate_items, parse_page
from app.utils.validation import normalize_vendor


bp = Blueprint("inventory", __name__, url_prefix="/inventory")


@bp.get("/<vendor>")
@login_required
def view_inventory(vendor: str):
    normalized = normalize_vendor(vendor)
    query = (request.args.get("q") or "").strip()
    sector = (request.args.get("sector") or "").strip()
    device_type = (request.args.get("device_type") or "").strip()

    all_devices = list_devices(normalized, query=query, sector=sector, device_type=device_type)
    pager = paginate_items(all_devices, parse_page(request.args.get("page")), per_page=20)
    return render_template(
        "inventory/list.html",
        vendor=normalized,
        devices=pager["items"],
        total=pager["total_items"],
        query=query,
        sectors=distinct_values(normalized, "sector_name"),
        device_types=distinct_values(normalized, "device_type"),
        selected_sector=sector,
        selected_device_type=device_type,
        latest_run=latest_successful_run(normalized),
        scan_state=scan_readiness(current_app, normalized),
        pager=pager,
    )


@bp.post("/run/<vendor>")
@role_required("operator", "admin")
def run_manual_scan(vendor: str):
    normalized = normalize_vendor(vendor)
    requested_action = (request.form.get("action") or "run").strip().lower()
    restart_requested = requested_action == "restart"
    scan_state = scan_readiness(current_app, normalized)
    blocked = not scan_state["targets"] or not scan_state["credentials_configured"] or (scan_state["running"] and not restart_requested)
    if blocked:
        audit_service.log_event(
            "scan.manual_rejected",
            "job",
            None,
            {
                "vendor": normalized,
                "outcome": "blocked",
                "summary": scan_state["reason"],
                "targets": scan_state["targets"],
                "credentials_configured": scan_state["credentials_configured"],
            },
        )
        flash(f"Manual scan blocked: {scan_state['reason']}", "danger")
        return redirect(url_for("inventory.view_inventory", vendor=normalized))

    job_manager = request.environ["job_manager"]
    if restart_requested:
        job_id, replaced_job_ids = job_manager.restart_scan(normalized, request.environ.get("current_user_id"), "manual")
        audit_service.log_event(
            "scan.manual_restarted",
            "job",
            str(job_id),
            {
                "vendor": normalized,
                "outcome": "queued",
                "summary": f"{normalized.title()} scan restart queued.",
                "targets": scan_state["targets"],
                "credentials_configured": scan_state["credentials_configured"],
                "trigger_source": "manual",
                "replaced_job_ids": replaced_job_ids,
            },
        )
        if replaced_job_ids:
            replaced_label = ", ".join(f"#{job}" for job in replaced_job_ids)
            flash(
                f"{normalized.title()} restart queued as job #{job_id}. Replacing {replaced_label}.",
                "success",
            )
        else:
            flash(f"{normalized.title()} scan queued as job #{job_id}.", "success")
        return redirect(url_for("inventory.view_inventory", vendor=normalized))

    accepted, job_id = job_manager.enqueue_scan(normalized, request.environ.get("current_user_id"), "manual")
    if accepted:
        audit_service.log_event(
            "scan.manual_triggered",
            "job",
            str(job_id),
            {
                "vendor": normalized,
                "outcome": "queued",
                "summary": f"{normalized.title()} manual scan queued.",
                "targets": scan_state["targets"],
                "credentials_configured": scan_state["credentials_configured"],
                "trigger_source": "manual",
            },
        )
        flash(f"{normalized.title()} scan queued as job #{job_id}.", "success")
    else:
        audit_service.log_event(
            "scan.manual_rejected",
            "job",
            str(job_id) if job_id else None,
            {
                "vendor": normalized,
                "outcome": "blocked",
                "summary": f"{normalized.title()} scan request rejected because another scan is already queued or running.",
                "targets": scan_state["targets"],
            },
        )
        flash(f"A {normalized} scan is already queued or running.", "warning")
    return redirect(url_for("inventory.view_inventory", vendor=normalized))
