from __future__ import annotations

from flask import Blueprint, current_app, jsonify, render_template, request

from app.utils.auth import login_required
from app.utils.helpers import paginate_items, parse_page


bp = Blueprint("monitoring", __name__, url_prefix="/monitoring")


@bp.get("/")
@login_required
def index():
    service = current_app.extensions["monitoring_service"]
    snapshot = service.get_snapshot()
    if not snapshot.get("checked_at"):
        service.request_refresh()
    sectors = snapshot["groups"]["sectors"]
    switches = snapshot["groups"]["switches"]
    priority = {
        "offline_sectors": [item for item in sectors if item.get("status") == "offline"],
        "offline_switches": [item for item in switches if item.get("status") == "offline"],
    }
    sectors_pager = paginate_items(sectors, parse_page(request.args.get("sectors_page")), per_page=20)
    switches_pager = paginate_items(switches, parse_page(request.args.get("switches_page")), per_page=20)
    snapshot = {
        **snapshot,
        "priority": priority,
        "groups": {
            **snapshot["groups"],
            "sectors": sectors_pager["items"],
            "switches": switches_pager["items"],
        },
    }
    return render_template("monitoring/index.html", snapshot=snapshot, sectors_pager=sectors_pager, switches_pager=switches_pager)


@bp.get("/status")
@login_required
def status():
    service = current_app.extensions["monitoring_service"]
    if not service.get_snapshot().get("checked_at"):
        service.request_refresh()
    return jsonify(service.get_snapshot())
