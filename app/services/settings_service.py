from __future__ import annotations

from pathlib import Path


def build_settings_snapshot(app) -> dict:
    config = app.config

    runtime = [
        {"label": "Host", "value": config["HOST"]},
        {"label": "Port", "value": str(config["PORT"])},
        {"label": "Log Level", "value": config["LOG_LEVEL"]},
        {"label": "Preferred Scheme", "value": config["PREFERRED_URL_SCHEME"]},
        {"label": "Proxy Trust", "value": "Enabled" if config["TRUST_PROXY"] else "Disabled"},
        {"label": "Cookie SameSite", "value": config["SESSION_COOKIE_SAMESITE"]},
        {"label": "Secure Cookies", "value": "Enabled" if config["SESSION_COOKIE_SECURE"] else "Disabled"},
    ]

    telemetry = [
        {"label": "Scheduler", "value": "Enabled" if config["SCHEDULER_ENABLED"] else "Disabled"},
        {"label": "Cambium Scan Interval", "value": f"{config['CAMBIUM_SCAN_INTERVAL_MINUTES']} min"},
        {"label": "Ubiquiti Scan Interval", "value": f"{config['UBIQUITI_SCAN_INTERVAL_MINUTES']} min"},
        {"label": "Scheduler Tick", "value": f"{config['SCHEDULER_TICK_SECONDS']} sec"},
        {"label": "Job Workers", "value": str(config["JOB_MAX_WORKERS"])},
        {"label": "Stale Threshold", "value": f"{config['STALE_SCAN_THRESHOLD_MINUTES']} min"},
    ]

    paths = [
        _path_item("Config Directory", Path(config["SCAN_TARGETS_FILE"]).parent),
        _path_item("Scan Targets", Path(config["SCAN_TARGETS_FILE"])),
        _path_item("Ultra Seed", Path(config["SWITCH_INVENTORY_SEED_FILE"])),
        _path_item("HT Seed", Path(config["HT_SWITCH_INVENTORY_SEED_FILE"])),
        _path_item("Instance Directory", Path(config["INSTANCE_PATH"])),
        _path_item("Database", Path(config["DATABASE_PATH"])),
        _path_item("Logs", Path(config["LOG_DIR"])),
    ]

    security = [
        {"label": "Authentication", "value": "Local sign-in enabled"},
        {"label": "CSRF Protection", "value": "Enabled"},
        {"label": "Roles", "value": "viewer / operator / admin"},
        {"label": "Bootstrap Admin", "value": config["BOOTSTRAP_ADMIN_USERNAME"]},
        {"label": "Cambium Credentials", "value": _credential_state(config["CAMBIUM_USERNAME"], config["CAMBIUM_PASSWORD"])},
        {"label": "Ubiquiti Credentials", "value": _credential_state(config["UBIQUITI_USERNAME"], config["UBIQUITI_PASSWORD"])},
        {"label": "Ultra Switch Credentials", "value": _credential_state(config["ULTRA_SWITCH_USERNAME"], config["ULTRA_SWITCH_PASSWORD"])},
        {"label": "HT Switch Credentials", "value": _credential_state(config["HT_SWITCH_USERNAME"], config["HT_SWITCH_PASSWORD"])},
    ]

    return {
        "runtime": runtime,
        "telemetry": telemetry,
        "paths": paths,
        "security": security,
    }


def _path_item(label: str, path: Path) -> dict:
    return {
        "label": label,
        "value": str(path),
        "exists": path.exists(),
    }


def _credential_state(username: str, password: str) -> str:
    if username and password:
        return "Configured"
    if username or password:
        return "Partial"
    return "Missing"
