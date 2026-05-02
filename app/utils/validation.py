from __future__ import annotations

import ipaddress
import re


DESCRIPTION_RE = re.compile(r"^[A-Za-z0-9 _./()#+:-]{3,80}$")
PORT_RE = re.compile(r"^(GigabitEthernet0/0|GE1/0)/\d+$")
TEXT_RE = re.compile(r"^[A-Za-z0-9 _./()#+:-]{2,80}$")
NOTES_RE = re.compile(r"^[A-Za-z0-9 _./()#+:,\-]{0,160}$")
USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,40}$")
DAILY_TIME_RE = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")
VALID_ROLES = {"viewer", "operator", "admin"}
VALID_UI_PREFERENCES = {"dark", "light"}


class FormValidationError(ValueError):
    def __init__(self, message: str, field_errors: dict[str, str] | None = None):
        super().__init__(message)
        self.field_errors = field_errors or {}


def is_valid_ip(value: str) -> bool:
    try:
        ipaddress.ip_address(value)
        return True
    except ValueError:
        return False


def validate_description(value: str) -> str:
    cleaned = (value or "").strip()
    if not DESCRIPTION_RE.match(cleaned):
        raise ValueError(
            "Description must be 3-80 chars and use letters, numbers, spaces, or common network punctuation."
        )
    return cleaned


def validate_port_name(value: str) -> str:
    cleaned = (value or "").strip()
    if not PORT_RE.match(cleaned):
        raise ValueError("Invalid port selection.")
    return cleaned


def validate_positive_int(value: str, label: str) -> int:
    cleaned = (value or "").strip()
    if not cleaned.isdigit():
        raise ValueError(f"Select a valid {label}.")
    parsed = int(cleaned)
    if parsed <= 0:
        raise ValueError(f"Select a valid {label}.")
    return parsed


def validate_switch_inventory_payload(payload: dict) -> dict:
    errors: dict[str, str] = {}

    try:
        inventory_type = normalize_inventory_type(payload.get("inventory_type", ""))
    except ValueError:
        inventory_type = ""
        errors["inventory_type"] = "Choose a supported inventory type."

    name = _required_text(payload.get("name", ""), "Switch name", errors, "name")
    ip = (payload.get("ip") or "").strip()
    if not ip:
        errors["ip"] = "IP address is required."
    elif not is_valid_ip(ip):
        errors["ip"] = "Enter a valid IPv4 or IPv6 address."

    city = _optional_text(payload.get("city", ""), "City", errors, "city")
    area = _optional_text(payload.get("area", ""), "Area", errors, "area")
    site = _optional_text(payload.get("site", ""), "Site", errors, "site")
    notes = _optional_notes(payload.get("notes", ""), errors, "notes")

    if inventory_type == "ultra":
        if not city:
            errors["city"] = "City is required for Ultra inventory records."
        if not area:
            errors["area"] = "Area is required for Ultra inventory records."
    elif inventory_type == "ht":
        if not site:
            errors["site"] = "Site is required for HT inventory records."

    if errors:
        raise FormValidationError("Correct the highlighted fields and try again.", errors)

    return {
        "inventory_type": inventory_type,
        "city": city,
        "area": area,
        "site": site,
        "name": name,
        "ip": ip,
        "notes": notes,
    }


def validate_user_payload(payload: dict) -> dict:
    errors: dict[str, str] = {}

    username = (payload.get("username") or "").strip()
    if not username:
        errors["username"] = "Username is required."
    elif not USERNAME_RE.match(username):
        errors["username"] = "Username must be 3-40 chars and use letters, numbers, dots, dashes, or underscores."

    role = (payload.get("role") or "").strip().lower()
    if role not in VALID_ROLES:
        errors["role"] = "Choose viewer, operator, or admin."

    raw_ui_preference = payload.get("ui_preference")
    try:
        ui_preference = normalize_ui_preference(raw_ui_preference, default="dark")
    except ValueError:
        ui_preference = "dark"
        errors["ui_preference"] = "Choose white/red or black/blue theme."

    password = payload.get("password") or ""
    if len(password) < 8:
        errors["password"] = "Password must be at least 8 characters."
    elif len(password) > 128:
        errors["password"] = "Password must be 128 characters or fewer."

    if errors:
        raise FormValidationError("Correct the highlighted fields and try again.", errors)

    return {
        "username": username,
        "role": role,
        "ui_preference": ui_preference,
        "password": password,
    }


def validate_ui_preference(value: str) -> str:
    return normalize_ui_preference(value, default="dark")


def normalize_ui_preference(value: str | None, default: str = "dark") -> str:
    cleaned = (value or default).strip().lower()
    legacy_map = {
        "modern": "dark",
        "classic": "light",
        "dark": "dark",
        "light": "light",
    }
    normalized = legacy_map.get(cleaned)
    if normalized not in VALID_UI_PREFERENCES:
        raise ValueError("Choose a supported UI mode.")
    return normalized


def validate_daily_schedule_payload(payload: dict) -> dict:
    errors: dict[str, str] = {}

    vendor = (payload.get("vendor") or "").strip().lower()
    if vendor not in {"cambium", "ubiquiti"}:
        errors["vendor"] = "Choose a supported vendor."

    enabled = payload.get("enabled") in {True, "true", "1", "on", "yes"}
    daily_time = (payload.get("daily_time") or "").strip()

    if enabled and not daily_time:
        errors["daily_time"] = "Daily time is required when the schedule is enabled."
    elif daily_time and not DAILY_TIME_RE.match(daily_time):
        errors["daily_time"] = "Use 24-hour time in HH:MM format."

    if errors:
        raise FormValidationError("Correct the highlighted fields and try again.", errors)

    return {
        "vendor": vendor,
        "enabled": enabled,
        "daily_time": daily_time,
    }


def normalize_vendor(value: str) -> str:
    cleaned = (value or "").strip().lower()
    if cleaned not in {"cambium", "ubiquiti"}:
        raise ValueError("Unsupported vendor.")
    return cleaned


def normalize_inventory_type(value: str) -> str:
    cleaned = (value or "").strip().lower()
    if cleaned not in {"ultra", "ht"}:
        raise ValueError("Unsupported switch inventory type.")
    return cleaned


def _required_text(value: str, label: str, errors: dict[str, str], field_name: str) -> str:
    cleaned = (value or "").strip()
    if not cleaned:
        errors[field_name] = f"{label} is required."
        return ""
    if not TEXT_RE.match(cleaned):
        errors[field_name] = f"{label} must be 2-80 chars and use safe operational text."
    return cleaned


def _optional_text(value: str, label: str, errors: dict[str, str], field_name: str) -> str:
    cleaned = (value or "").strip()
    if cleaned and not TEXT_RE.match(cleaned):
        errors[field_name] = f"{label} must be 2-80 chars and use safe operational text."
    return cleaned


def _optional_notes(value: str, errors: dict[str, str], field_name: str) -> str:
    cleaned = (value or "").strip()
    if cleaned and not NOTES_RE.match(cleaned):
        errors[field_name] = "Notes must be 160 chars or fewer and use safe operational text."
    return cleaned
