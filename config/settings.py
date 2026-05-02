import os
from pathlib import Path
from datetime import timedelta


def load_env_file(root_path: Path) -> None:
    env_path = root_path / ".env"
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def build_settings(root_path: Path) -> dict:
    load_env_file(root_path)

    instance_path = Path(os.environ.get("INSTANCE_PATH", root_path / "instance"))
    config_path = Path(os.environ.get("APP_CONFIG_DIR", root_path / "config"))

    return {
        "APP_NAME": os.environ.get("APP_NAME", "Network Operations Console"),
        "ROOT_PATH": root_path,
        "INSTANCE_PATH": instance_path,
        "DATABASE_PATH": Path(os.environ.get("DATABASE_PATH", instance_path / "noc_console.sqlite3")),
        "LOG_DIR": Path(os.environ.get("LOG_DIR", instance_path / "logs")),
        "LOG_LEVEL": os.environ.get("LOG_LEVEL", "INFO").upper(),
        "HOST": os.environ.get("HOST", "127.0.0.1"),
        "PORT": _int("PORT", 8080),
        "SECRET_KEY": os.environ.get("SECRET_KEY", "").strip(),
        "SCAN_TARGETS_FILE": Path(os.environ.get("SCAN_TARGETS_FILE", config_path / "scan_targets.json")),
        "SWITCH_INVENTORY_SEED_FILE": Path(
            os.environ.get("SWITCH_INVENTORY_SEED_FILE", config_path / "switch_inventory.seed.json")
        ),
        "HT_SWITCH_INVENTORY_SEED_FILE": Path(
            os.environ.get("HT_SWITCH_INVENTORY_SEED_FILE", config_path / "ht_switch_inventory.seed.json")
        ),
        "CAMBIUM_USERNAME": os.environ.get("CAMBIUM_USERNAME", ""),
        "CAMBIUM_PASSWORD": os.environ.get("CAMBIUM_PASSWORD", ""),
        "UBIQUITI_USERNAME": os.environ.get("UBIQUITI_USERNAME", ""),
        "UBIQUITI_PASSWORD": os.environ.get("UBIQUITI_PASSWORD", ""),
        "ULTRA_SWITCH_USERNAME": os.environ.get("ULTRA_SWITCH_USERNAME", ""),
        "ULTRA_SWITCH_PASSWORD": os.environ.get("ULTRA_SWITCH_PASSWORD", ""),
        "HT_SWITCH_USERNAME": os.environ.get("HT_SWITCH_USERNAME", ""),
        "HT_SWITCH_PASSWORD": os.environ.get("HT_SWITCH_PASSWORD", ""),
        "BOOTSTRAP_ADMIN_USERNAME": os.environ.get("BOOTSTRAP_ADMIN_USERNAME", "admin"),
        "BOOTSTRAP_ADMIN_PASSWORD": os.environ.get("BOOTSTRAP_ADMIN_PASSWORD", ""),
        "BOOTSTRAP_ADMIN_ROLE": os.environ.get("BOOTSTRAP_ADMIN_ROLE", "admin"),
        "PLAYWRIGHT_HEADLESS": _bool("PLAYWRIGHT_HEADLESS", True),
        "SCHEDULER_ENABLED": _bool("SCHEDULER_ENABLED", True),
        "CAMBIUM_SCAN_INTERVAL_MINUTES": _int("CAMBIUM_SCAN_INTERVAL_MINUTES", 1440),
        "UBIQUITI_SCAN_INTERVAL_MINUTES": _int("UBIQUITI_SCAN_INTERVAL_MINUTES", 1440),
        "SCHEDULER_TICK_SECONDS": _int("SCHEDULER_TICK_SECONDS", 60),
        "JOB_MAX_WORKERS": _int("JOB_MAX_WORKERS", 2),
        "JOB_FAILURE_SAMPLE_LIMIT": _int("JOB_FAILURE_SAMPLE_LIMIT", 5),
        "STALE_SCAN_THRESHOLD_MINUTES": _int("STALE_SCAN_THRESHOLD_MINUTES", 1440),
        "MONITORING_ENABLED": _bool("MONITORING_ENABLED", True),
        "MONITOR_PING_COUNT": _int("MONITOR_PING_COUNT", 4),
        "MONITOR_REFRESH_SECONDS": _int("MONITOR_REFRESH_SECONDS", 30),
        "MONITOR_RETRY_DELAY_SECONDS": _int("MONITOR_RETRY_DELAY_SECONDS", 10),
        "MONITOR_PING_TIMEOUT_MS": _int("MONITOR_PING_TIMEOUT_MS", 1000),
        "MONITOR_MAX_WORKERS": _int("MONITOR_MAX_WORKERS", 16),
        "SESSION_IDLE_TIMEOUT_MINUTES": _int("SESSION_IDLE_TIMEOUT_MINUTES", 7),
        "PERMANENT_SESSION_LIFETIME": timedelta(minutes=_int("SESSION_IDLE_TIMEOUT_MINUTES", 7)),
        "SESSION_COOKIE_HTTPONLY": True,
        "SESSION_COOKIE_SAMESITE": os.environ.get("SESSION_COOKIE_SAMESITE", "Lax"),
        "SESSION_COOKIE_SECURE": _bool("SESSION_COOKIE_SECURE", False),
        "PREFERRED_URL_SCHEME": os.environ.get("PREFERRED_URL_SCHEME", "http"),
        "TRUST_PROXY": _bool("TRUST_PROXY", False),
        "TESTING": False,
    }
