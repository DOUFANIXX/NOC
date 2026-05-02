from __future__ import annotations

import json
from pathlib import Path


def load_targets(path: Path) -> dict:
    records = load_target_records(path)
    return {
        vendor: [item["ip"] for item in items]
        for vendor, items in records.items()
    }


def load_target_records(path: Path) -> dict:
    if not path.exists():
        return {"cambium": [], "ubiquiti": []}
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    return {
        "cambium": _normalize_target_entries(data.get("cambium", [])),
        "ubiquiti": _normalize_target_entries(data.get("ubiquiti", [])),
    }


def _normalize_target_entries(raw_items: list) -> list[dict]:
    normalized: list[dict] = []
    seen: set[str] = set()

    for item in raw_items:
        if isinstance(item, str):
            ip = item.strip()
            name = ""
        elif isinstance(item, dict):
            ip = str(item.get("ip", "")).strip()
            name = str(item.get("name", "")).strip()
        else:
            continue

        if not ip or ip in seen:
            continue
        seen.add(ip)
        normalized.append({"ip": ip, "name": name})

    return normalized
