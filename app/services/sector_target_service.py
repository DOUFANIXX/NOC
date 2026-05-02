from __future__ import annotations

from app.db import get_db
from app.utils.helpers import utcnow_iso
from app.utils.validation import normalize_vendor


def upsert_sector_targets(vendor: str, sectors: list[dict]) -> int:
    normalized = normalize_vendor(vendor)
    db = get_db()
    timestamp = utcnow_iso()
    processed = 0

    for sector in sectors:
        sector_ip = (sector.get("sector_ip") or "").strip()
        if not sector_ip:
            continue
        db.execute(
            """
            INSERT INTO sector_targets (
                vendor, sector_ip, sector_name, source_detail, last_seen_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(vendor, sector_ip) DO UPDATE SET
                sector_name=excluded.sector_name,
                source_detail=excluded.source_detail,
                last_seen_at=excluded.last_seen_at,
                updated_at=excluded.updated_at
            """,
            (
                normalized,
                sector_ip,
                (sector.get("sector_name") or "").strip() or None,
                (sector.get("source_detail") or "").strip() or None,
                sector.get("timestamp") or timestamp,
                timestamp,
            ),
        )
        processed += 1

    db.commit()
    return processed
