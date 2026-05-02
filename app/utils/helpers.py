from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from urllib.parse import urlencode


ISO_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def local_now() -> datetime:
    return datetime.now().astimezone()


def utcnow_iso() -> str:
    return utcnow().strftime(ISO_FORMAT)


def parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    for pattern in (ISO_FORMAT, "%Y-%m-%dT%H:%M:%SZ"):
        try:
            return datetime.strptime(value, pattern).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def humanize_timestamp(value: str | None) -> str:
    dt = parse_timestamp(value)
    if dt is None:
        return "Never"
    return dt.astimezone().strftime("%Y-%m-%d %H:%M:%S")


def parse_page(value: str | None, default: int = 1) -> int:
    try:
        page = int(value or default)
    except (TypeError, ValueError):
        return default
    return page if page > 0 else default


def paginate_items(items: Sequence, page: int, per_page: int = 20) -> dict:
    total_items = len(items)
    total_pages = max(1, (total_items + per_page - 1) // per_page)
    current_page = min(max(1, page), total_pages)
    start_index = (current_page - 1) * per_page
    end_index = start_index + per_page
    page_items = list(items[start_index:end_index])
    start_item = start_index + 1 if total_items else 0
    end_item = min(end_index, total_items)
    window_start = max(1, current_page - 2)
    window_end = min(total_pages, current_page + 2)

    return {
        "items": page_items,
        "page": current_page,
        "per_page": per_page,
        "total_items": total_items,
        "total_pages": total_pages,
        "has_prev": current_page > 1,
        "has_next": current_page < total_pages,
        "prev_page": current_page - 1 if current_page > 1 else 1,
        "next_page": current_page + 1 if current_page < total_pages else total_pages,
        "start_item": start_item,
        "end_item": end_item,
        "pages": list(range(window_start, window_end + 1)),
    }


def replace_query_params(args: Mapping[str, object], **updates: object) -> str:
    merged: dict[str, object] = {}
    for key in args.keys():
        values = args.getlist(key) if hasattr(args, "getlist") else [args[key]]
        merged[key] = values if len(values) > 1 else values[0]

    for key, value in updates.items():
        if value in (None, "", False):
            merged.pop(key, None)
            continue
        merged[key] = value

    if not merged:
        return ""
    return "?" + urlencode(merged, doseq=True)
