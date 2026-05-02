from __future__ import annotations

from flask import Blueprint, render_template, request

from app.services.audit_service import get_event, list_events, summarize_events
from app.utils.auth import role_required
from app.utils.helpers import paginate_items, parse_page


bp = Blueprint("audit", __name__, url_prefix="/audit")


@bp.get("/")
@role_required("operator", "admin")
def index():
    query = (request.args.get("q") or "").strip()
    all_events = list_events(limit=None, query=query)
    pager = paginate_items(all_events, parse_page(request.args.get("page")), per_page=20)
    events = pager["items"]
    selected_id = request.args.get("event_id", "").strip()
    selected_event = get_event(int(selected_id)) if selected_id.isdigit() else (events[0] if events else None)
    return render_template(
        "audit/index.html",
        query=query,
        events=events,
        selected_event=selected_event,
        summary=summarize_events(),
        pager=pager,
    )
