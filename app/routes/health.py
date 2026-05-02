from __future__ import annotations

from pathlib import Path

from flask import Blueprint, current_app, jsonify

from app.db import get_db


bp = Blueprint("health", __name__)


@bp.get("/healthz")
def healthcheck():
    return jsonify({"status": "ok"})


@bp.get("/readyz")
def readiness():
    checks = {
        "database": False,
        "scan_targets": Path(current_app.config["SCAN_TARGETS_FILE"]).exists(),
        "switch_inventory_seed": Path(current_app.config["SWITCH_INVENTORY_SEED_FILE"]).exists(),
        "ht_switch_inventory_seed": Path(current_app.config["HT_SWITCH_INVENTORY_SEED_FILE"]).exists(),
    }
    try:
        get_db().execute("SELECT 1").fetchone()
        checks["database"] = True
    except Exception:
        current_app.logger.exception("Readiness database check failed")

    ready = all(checks.values())
    status_code = 200 if ready else 503
    return jsonify({"status": "ready" if ready else "degraded", "checks": checks}), status_code
