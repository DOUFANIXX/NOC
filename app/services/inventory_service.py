from __future__ import annotations

import json

from flask import current_app

from app.db import get_db
from app.services.scan_target_service import load_target_records
from app.utils.helpers import utcnow_iso
from app.utils.validation import normalize_vendor


def upsert_devices(vendor: str, devices: list[dict]) -> int:
    normalized = normalize_vendor(vendor)
    db = get_db()
    timestamp = utcnow_iso()
    processed = 0

    for device in devices:
        mac = (device.get("mac") or "").strip()
        if not mac:
            continue
        db.execute(
            """
            INSERT INTO devices (
                vendor, mac, username, device_type, firmware, ip, rssi,
                sector_name, sector_ip, source_ip, raw_json, last_seen_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(vendor, mac) DO UPDATE SET
                username=excluded.username,
                device_type=excluded.device_type,
                firmware=excluded.firmware,
                ip=excluded.ip,
                rssi=excluded.rssi,
                sector_name=excluded.sector_name,
                sector_ip=excluded.sector_ip,
                source_ip=excluded.source_ip,
                raw_json=excluded.raw_json,
                last_seen_at=excluded.last_seen_at,
                updated_at=excluded.updated_at
            """,
            (
                normalized,
                mac,
                device.get("username"),
                device.get("device_type"),
                device.get("firmware"),
                device.get("ip"),
                device.get("rssi"),
                device.get("sector_name"),
                device.get("sector_ip"),
                device.get("source_ip"),
                json.dumps(device, sort_keys=True),
                device.get("timestamp") or timestamp,
                timestamp,
            ),
        )
        processed += 1

    db.commit()
    return processed


def list_devices(vendor: str, query: str = "", sector: str = "", device_type: str = "") -> list[dict]:
    normalized = normalize_vendor(vendor)
    rows = get_db().execute(
        """
        SELECT id, vendor, mac, username, device_type, firmware, ip, rssi,
               sector_name, sector_ip, source_ip, last_seen_at, updated_at
        FROM devices
        WHERE vendor = ?
        ORDER BY LOWER(COALESCE(username, mac)) ASC
        """,
        (normalized,),
    ).fetchall()
    devices = [_normalize_device_record(normalized, dict(row)) for row in rows]

    normalized_query = query.strip().lower()
    if normalized_query:
        devices = [
            device
            for device in devices
            if normalized_query in (device.get("mac") or "").lower()
            or normalized_query in (device.get("username") or "").lower()
            or normalized_query in (device.get("ip") or "").lower()
            or normalized_query in (device.get("sector_name") or "").lower()
        ]
    if sector:
        devices = [device for device in devices if (device.get("sector_name") or "") == sector]
    if device_type:
        devices = [device for device in devices if (device.get("device_type") or "") == device_type]

    return devices


def distinct_values(vendor: str, column: str) -> list[str]:
    normalized = normalize_vendor(vendor)
    if column not in {"sector_name", "device_type"}:
        return []
    if column == "sector_name":
        return sorted(
            {
                device["sector_name"]
                for device in list_devices(normalized)
                if device.get("sector_name")
            },
            key=str.lower,
        )
    rows = get_db().execute(
        """
        SELECT DISTINCT device_type AS value
        FROM devices
        WHERE vendor = ? AND device_type IS NOT NULL AND device_type != ''
        ORDER BY value
        """,
        (normalized,),
    ).fetchall()
    return [row["value"] for row in rows]


def counts_by_vendor() -> dict[str, int]:
    rows = get_db().execute("SELECT vendor, COUNT(*) AS total FROM devices GROUP BY vendor").fetchall()
    counts = {"cambium": 0, "ubiquiti": 0}
    for row in rows:
        counts[row["vendor"]] = row["total"]
    return counts


def _normalize_device_record(vendor: str, device: dict) -> dict:
    configured_name = _configured_sector_names(vendor).get((device.get("sector_ip") or "").strip())
    if configured_name:
        device["sector_name"] = configured_name
    return device


def _configured_sector_names(vendor: str) -> dict[str, str]:
    try:
        target_records = load_target_records(current_app.config["SCAN_TARGETS_FILE"]).get(vendor, [])
    except Exception:
        return {}
    return {
        (item.get("ip") or "").strip(): (item.get("name") or "").strip()
        for item in target_records
        if (item.get("ip") or "").strip() and (item.get("name") or "").strip()
    }
