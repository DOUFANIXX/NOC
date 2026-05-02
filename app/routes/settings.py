from __future__ import annotations

from flask import Blueprint, current_app, render_template

from app.services.settings_service import build_settings_snapshot
from app.utils.auth import role_required


bp = Blueprint("settings", __name__, url_prefix="/settings")


@bp.get("/")
@role_required("operator", "admin")
def index():
    return render_template("settings/index.html", sections=build_settings_snapshot(current_app))
