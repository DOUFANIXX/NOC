from __future__ import annotations

from flask import Blueprint, current_app, render_template, request

from app.services.dashboard_service import build_dashboard
from app.utils.auth import role_required
from app.utils.helpers import paginate_items, parse_page


bp = Blueprint("dashboard", __name__)


@bp.get("/")
@role_required("operator", "admin")
def index():
    context = build_dashboard(current_app)
    jobs_pager = paginate_items(context["recent_jobs"], parse_page(request.args.get("jobs_page")), per_page=4)
    audit_pager = paginate_items(context["recent_audit_events"], parse_page(request.args.get("audit_page")), per_page=4)
    context["recent_jobs"] = jobs_pager["items"]
    context["recent_audit_events"] = audit_pager["items"]
    context["jobs_pager"] = jobs_pager
    context["audit_pager"] = audit_pager
    return render_template("dashboard/index.html", **context)
