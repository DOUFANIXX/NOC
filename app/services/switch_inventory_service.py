from __future__ import annotations

import json
from pathlib import Path

from flask import current_app

from app.db import get_db
from app.utils.helpers import utcnow_iso
from app.utils.validation import is_valid_ip, normalize_inventory_type


def _seed_path(app, inventory_type: str) -> Path:
    normalized = normalize_inventory_type(inventory_type)
    if normalized == "ultra":
        return Path(app.config["SWITCH_INVENTORY_SEED_FILE"])
    return Path(app.config["HT_SWITCH_INVENTORY_SEED_FILE"])


def _load_seed_data(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"Seed file {path} must contain a JSON object.")
    return data


def _write_seed_data(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)
        handle.write("\n")


def _rows_from_seed_data(inventory_type: str) -> list[dict]:
    normalized = normalize_inventory_type(inventory_type)
    data = _load_seed_data(_seed_path(current_app, normalized))
    rows: list[dict] = []
    if normalized == "ultra":
        for city, areas in data.items():
            for area, switches in areas.items():
                for name, info in switches.items():
                    rows.append(
                        {
                            "inventory_type": normalized,
                            "city": city,
                            "area": area,
                            "site": None,
                            "name": name,
                            "ip": info["ip"],
                            "notes": info.get("notes", ""),
                        }
                    )
        return rows

    for site, switches in data.items():
        for name, info in switches.items():
            rows.append(
                {
                    "inventory_type": normalized,
                    "city": None,
                    "area": None,
                    "site": site,
                    "name": name,
                    "ip": info["ip"],
                    "notes": info.get("notes", ""),
                }
            )
    return rows


def _sync_inventory_type_from_seed(app, inventory_type: str) -> None:
    normalized = normalize_inventory_type(inventory_type)
    path = _seed_path(app, normalized)
    if not path.exists():
        return

    rows = _rows_from_seed_data(normalized)
    timestamp = utcnow_iso()
    db = get_db()
    existing_rows = db.execute(
        """
        SELECT id, ip
        FROM switch_inventory
        WHERE inventory_type = ?
        """,
        (normalized,),
    ).fetchall()
    existing_by_ip = {row["ip"]: row["id"] for row in existing_rows}
    expected_ips = {row["ip"] for row in rows}

    for row in rows:
        existing_id = existing_by_ip.get(row["ip"])
        if existing_id is not None:
            db.execute(
                """
                UPDATE switch_inventory
                SET city = ?, area = ?, site = ?, name = ?, notes = ?, updated_at = ?
                WHERE id = ?
                """,
                (row["city"], row["area"], row["site"], row["name"], row["notes"], timestamp, existing_id),
            )
            continue

        db.execute(
            """
            INSERT INTO switch_inventory (
                inventory_type, city, area, site, name, ip, notes, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row["inventory_type"],
                row["city"],
                row["area"],
                row["site"],
                row["name"],
                row["ip"],
                row["notes"],
                timestamp,
                timestamp,
            ),
        )

    if expected_ips:
        placeholders = ",".join("?" for _ in expected_ips)
        db.execute(
            f"DELETE FROM switch_inventory WHERE inventory_type = ? AND ip NOT IN ({placeholders})",
            (normalized, *expected_ips),
        )
    else:
        db.execute("DELETE FROM switch_inventory WHERE inventory_type = ?", (normalized,))
    db.commit()


def _load_inventory_seed(app, inventory_type: str) -> tuple[Path, dict]:
    path = _seed_path(app, inventory_type)
    return path, _load_seed_data(path)


def seed_inventory_from_files(app) -> None:
    for inventory_type in ("ultra", "ht"):
        _sync_inventory_type_from_seed(app, inventory_type)


def _lookup_switch_id(inventory_type: str, ip: str) -> int:
    row = get_db().execute(
        """
        SELECT id
        FROM switch_inventory
        WHERE inventory_type = ? AND ip = ?
        """,
        (normalize_inventory_type(inventory_type), ip),
    ).fetchone()
    if not row:
        raise ValueError("Switch record was not found after saving.")
    return row["id"]


def _upsert_switch_in_seed(payload: dict) -> None:
    inventory_type = normalize_inventory_type(payload["inventory_type"])
    path, data = _load_inventory_seed(current_app, inventory_type)
    entry = {"ip": payload["ip"].strip()}
    notes = (payload.get("notes") or "").strip()
    if notes:
        entry["notes"] = notes

    if inventory_type == "ultra":
        city = payload.get("city") or ""
        area = payload.get("area") or ""
        data.setdefault(city, {}).setdefault(area, {})[payload["name"].strip()] = entry
    else:
        site = payload.get("site") or ""
        data.setdefault(site, {})[payload["name"].strip()] = entry

    _write_seed_data(path, data)


def _delete_switch_from_seed(record: dict) -> None:
    inventory_type = normalize_inventory_type(record["inventory_type"])
    path, data = _load_inventory_seed(current_app, inventory_type)

    if inventory_type == "ultra":
        city = record["city"]
        area = record["area"]
        area_bucket = data.get(city, {}).get(area, {})
        area_bucket.pop(record["name"], None)
        if city in data and area in data[city] and not data[city][area]:
            data[city].pop(area, None)
        if city in data and not data[city]:
            data.pop(city, None)
    else:
        site = record["site"]
        site_bucket = data.get(site, {})
        site_bucket.pop(record["name"], None)
        if site in data and not data[site]:
            data.pop(site, None)

    _write_seed_data(path, data)


def get_grouped_inventory(inventory_type: str) -> dict:
    normalized = normalize_inventory_type(inventory_type)
    rows = get_db().execute(
        """
        SELECT id, inventory_type, city, area, site, name, ip, notes
        FROM switch_inventory
        WHERE inventory_type = ?
        ORDER BY COALESCE(city, site, ''), COALESCE(area, ''), name
        """,
        (normalized,),
    ).fetchall()

    if normalized == "ultra":
        grouped: dict[str, dict[str, list[dict]]] = {}
        for row in rows:
            item = dict(row)
            grouped.setdefault(item["city"], {}).setdefault(item["area"], []).append(item)
        return grouped

    grouped: dict[str, list[dict]] = {}
    for row in rows:
        item = dict(row)
        grouped.setdefault(item["site"], []).append(item)
    return grouped


def list_inventory(inventory_type: str | None = None) -> list[dict]:
    sql = """
        SELECT id, inventory_type, city, area, site, name, ip, notes, created_at, updated_at
        FROM switch_inventory
    """
    params: tuple = ()
    if inventory_type:
        sql += " WHERE inventory_type = ?"
        params = (normalize_inventory_type(inventory_type),)
    sql += " ORDER BY inventory_type, COALESCE(city, site, ''), COALESCE(area, ''), name"
    return [dict(row) for row in get_db().execute(sql, params).fetchall()]


def get_switch_record(switch_id: int) -> dict | None:
    row = get_db().execute(
        """
        SELECT id, inventory_type, city, area, site, name, ip, notes
        FROM switch_inventory
        WHERE id = ?
        """,
        (switch_id,),
    ).fetchone()
    return dict(row) if row else None


def add_switch_record(payload: dict) -> int:
    inventory_type = normalize_inventory_type(payload["inventory_type"])
    ip = payload["ip"].strip()
    if not is_valid_ip(ip):
        raise ValueError("Invalid IP address.")

    name = payload["name"].strip()
    if len(name) < 2:
        raise ValueError("Switch name is too short.")

    _upsert_switch_in_seed(payload)
    _sync_inventory_type_from_seed(current_app, inventory_type)
    return _lookup_switch_id(inventory_type, ip)


def delete_switch_record(switch_id: int) -> dict | None:
    record = get_switch_record(switch_id)
    if not record:
        return None
    _delete_switch_from_seed(record)
    _sync_inventory_type_from_seed(current_app, record["inventory_type"])
    return record
