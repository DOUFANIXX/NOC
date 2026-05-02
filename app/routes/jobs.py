from __future__ import annotations

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for

from app.services import audit_service
from app.services.jobs_service import list_recent_jobs, summarize_jobs
from app.services.scan_schedule_service import list_schedules, save_schedule
from app.utils.auth import role_required
from app.utils.helpers import paginate_items, parse_page
from app.utils.validation import FormValidationError, validate_daily_schedule_payload


bp = Blueprint("jobs", __name__, url_prefix="/jobs")


@bp.get("/")
@role_required("operator", "admin")
def list_jobs():
    all_jobs = list_recent_jobs(limit=None)
    pager = paginate_items(all_jobs, parse_page(request.args.get("page")), per_page=20)
    return render_template(
        "jobs/list.html",
        jobs=pager["items"],
        summary=summarize_jobs(current_app.config["STALE_SCAN_THRESHOLD_MINUTES"]),
        pager=pager,
    )


@bp.route("/schedule", methods=["GET", "POST"])
@role_required("operator", "admin")
def schedule():
    form_errors: dict[str, dict[str, str]] = {}
    page_feedback = None

    if request.method == "POST":
        payload = {
            "vendor": request.form.get("vendor", ""),
            "enabled": request.form.get("enabled") == "on",
            "daily_time": request.form.get("daily_time", ""),
        }
        try:
            cleaned = validate_daily_schedule_payload(payload)
            schedule_record = save_schedule(cleaned["vendor"], cleaned["enabled"], cleaned["daily_time"])
            audit_service.log_event(
                "schedule.scan_updated",
                "scan_schedule",
                schedule_record["vendor"],
                {
                    "outcome": "success",
                    "summary": (
                        f"{schedule_record['vendor'].title()} daily schedule set to {schedule_record['daily_time']}."
                        if schedule_record["enabled"] and schedule_record["daily_time"]
                        else f"{schedule_record['vendor'].title()} daily schedule disabled."
                    ),
                    "vendor": schedule_record["vendor"],
                    "enabled": schedule_record["enabled"],
                    "daily_time": schedule_record["daily_time"],
                },
            )
            flash("Schedule updated.", "success")
            return redirect(url_for("jobs.schedule"))
        except FormValidationError as exc:
            vendor = (payload["vendor"] or "").strip().lower()
            if vendor:
                form_errors[vendor] = exc.field_errors
            page_feedback = {"tone": "warning", "title": "Validation error", "message": str(exc)}
        except Exception as exc:
            page_feedback = {"tone": "danger", "title": "Schedule update failed", "message": str(exc)}

    return render_template(
        "jobs/schedule.html",
        schedules=list_schedules(),
        form_errors=form_errors,
        page_feedback=page_feedback,
        scheduler_enabled=current_app.config["SCHEDULER_ENABLED"],
        scheduler_tick_seconds=current_app.config["SCHEDULER_TICK_SECONDS"],
    )
