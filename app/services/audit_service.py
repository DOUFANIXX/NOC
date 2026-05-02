from __future__ import annotations

import json
from datetime import timedelta

from flask import g, has_request_context, request

from app.db import get_db
from app.utils.helpers import parse_timestamp, utcnow, utcnow_iso


def log_event(action: str, resource_type: str, resource_id: str | None = None, details: dict | None = None) -> None:
    user = getattr(g, "user", None)
    db = get_db()
    db.execute(
        """
        INSERT INTO audit_logs (
            actor_user_id, actor_username, action, resource_type, resource_id,
            details_json, remote_addr, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user["id"] if user else None,
            user["username"] if user else "system",
            action,
            resource_type,
            resource_id,
            json.dumps(details or {}, sort_keys=True),
            request.remote_addr if has_request_context() else None,
            utcnow_iso(),
        ),
    )
    db.commit()


def recent_events(limit: int = 10) -> list[dict]:
    rows = get_db().execute(
        """
        SELECT id, actor_username, action, resource_type, resource_id, details_json, created_at
        FROM audit_logs
        ORDER BY id DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [_enrich_event(dict(row)) for row in rows]


def list_events(limit: int | None = 100, query: str = "") -> list[dict]:
    sql = """
        SELECT id, actor_username, action, resource_type, resource_id, details_json, remote_addr, created_at
        FROM audit_logs
    """
    params: list[str | int] = []
    if query:
        sql += """
            WHERE actor_username LIKE ?
               OR action LIKE ?
               OR resource_type LIKE ?
               OR COALESCE(resource_id, '') LIKE ?
               OR COALESCE(details_json, '') LIKE ?
        """
        pattern = f"%{query}%"
        params.extend([pattern, pattern, pattern, pattern, pattern])
    sql += " ORDER BY id DESC"
    if limit is not None:
        sql += " LIMIT ?"
        params.append(limit)
    rows = get_db().execute(sql, tuple(params)).fetchall()
    events = [dict(row) for row in rows]
    return [_enrich_event(event) for event in events]


def get_event(event_id: int) -> dict | None:
    row = get_db().execute(
        """
        SELECT id, actor_username, action, resource_type, resource_id, details_json, remote_addr, created_at
        FROM audit_logs
        WHERE id = ?
        """,
        (event_id,),
    ).fetchone()
    if row is None:
        return None
    return _enrich_event(dict(row))


def summarize_events() -> dict:
    db = get_db()
    total = db.execute("SELECT COUNT(*) FROM audit_logs").fetchone()[0]
    critical = db.execute(
        """
        SELECT COUNT(*)
        FROM audit_logs
        WHERE action LIKE '%failed%'
           OR action LIKE '%deny%'
           OR action LIKE '%error%'
        """
    ).fetchone()[0]

    latest_row = db.execute(
        """
        SELECT created_at
        FROM audit_logs
        ORDER BY id DESC
        LIMIT 1
        """
    ).fetchone()
    latest_at = latest_row["created_at"] if latest_row else None
    latest_dt = parse_timestamp(latest_at)
    recent_threshold = utcnow() - timedelta(hours=24)
    recent_count = db.execute(
        """
        SELECT COUNT(*)
        FROM audit_logs
        WHERE created_at >= ?
        """,
        (recent_threshold.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),),
    ).fetchone()[0]

    top_actor_row = db.execute(
        """
        SELECT actor_username, COUNT(*) AS count
        FROM audit_logs
        GROUP BY actor_username
        ORDER BY count DESC, actor_username ASC
        LIMIT 1
        """
    ).fetchone()

    return {
        "total": total,
        "critical": critical,
        "recent_24h": recent_count,
        "latest_at": latest_at,
        "is_live": latest_dt is not None and latest_dt >= recent_threshold,
        "top_actor": dict(top_actor_row) if top_actor_row else None,
    }


def _load_details(raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"raw": raw}


def _enrich_event(event: dict) -> dict:
    details = _load_details(event.get("details_json"))
    event["details"] = details
    event["outcome"] = _derive_outcome(event.get("action", ""), details)
    event["summary"] = _build_summary(event, details)
    event["target_label"] = details.get("switch") or details.get("name") or event.get("resource_id") or "-"
    return event


def _derive_outcome(action: str, details: dict) -> str:
    if details.get("outcome"):
        return str(details["outcome"])
    lowered = action.lower()
    if any(token in lowered for token in ("failed", "rejected", "denied")):
        return "failed"
    if any(token in lowered for token in ("completed", "deleted", "added", "triggered")):
        return "success"
    return "info"


def _build_summary(event: dict, details: dict) -> str:
    if details.get("summary"):
        return str(details["summary"])
    if event.get("resource_type") == "switch":
        switch = details.get("switch") or event.get("resource_id") or "switch"
        port = details.get("port")
        return f"{switch} {port}".strip()
    if event.get("resource_type") == "job":
        vendor = details.get("vendor") or event.get("resource_id") or "job"
        return f"{vendor} job event"
    if event.get("resource_type") == "switch_inventory":
        name = details.get("name") or event.get("resource_id") or "inventory record"
        ip = details.get("ip")
        return f"{name} ({ip})" if ip else str(name)
    return event.get("action", "")
