from __future__ import annotations

import copy
import platform
import re
import subprocess
import threading
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

from app.db import get_db
from app.services.scan_target_service import load_target_records
from app.services.switch_inventory_service import list_inventory
from app.utils.helpers import utcnow, utcnow_iso


WINDOWS_RECEIVED_RE = re.compile(r"Received = (\d+)", re.IGNORECASE)
WINDOWS_LOST_RE = re.compile(r"Lost = (\d+)", re.IGNORECASE)
WINDOWS_AVG_RE = re.compile(r"Average = (\d+)ms", re.IGNORECASE)
POSIX_PACKET_RE = re.compile(r"(\d+)\s+packets transmitted,\s+(\d+)\s+(?:packets )?received", re.IGNORECASE)
POSIX_LOSS_RE = re.compile(r"(\d+(?:\.\d+)?)%\s+packet loss", re.IGNORECASE)
POSIX_AVG_RE = re.compile(r"=\s*[\d.]+/([\d.]+)/[\d.]+/[\d.]+", re.IGNORECASE)
GENERIC_TARGET_LABEL_RE = re.compile(r"^(?:cambium|ubiquiti)\s+target\s+\d+$", re.IGNORECASE)


def build_monitor_targets(app) -> list[dict]:
    sector_labels = _sector_labels_by_vendor_and_ip()
    discovered: list[dict] = []

    target_records = load_target_records(app.config["SCAN_TARGETS_FILE"])
    for vendor in ("cambium", "ubiquiti"):
        for target in target_records.get(vendor, []):
            ip = target["ip"]
            metadata = sector_labels.get((vendor, ip), {})
            configured_name = _configured_target_name(target.get("name"))
            label = configured_name or metadata.get("sector_name") or _fallback_target_label(vendor, ip)
            detail = "Configured scan target"
            if metadata.get("device_count"):
                detail = f"{metadata['device_count']} subscriber records seen on latest inventory"
            elif metadata.get("source_detail"):
                detail = f"Name captured from {metadata['source_detail']}"
            discovered.append(
                {
                    "target_id": f"sector:{vendor}:{ip}",
                    "category": "sector",
                    "group": vendor.title(),
                    "name": label,
                    "ip": ip,
                    "detail": detail,
                    "location": "",
                }
            )

    for record in list_inventory():
        location = ", ".join(part for part in (record.get("city"), record.get("area"), record.get("site")) if part)
        detail = location or (record.get("notes") or "").strip() or "Tracked switch inventory"
        discovered.append(
            {
                "target_id": f"switch:{record['inventory_type']}:{record['id']}",
                "category": "switch",
                "group": record["inventory_type"].upper(),
                "name": record["name"],
                "ip": record["ip"],
                "detail": detail,
                "location": location,
            }
        )

    return sorted(
        discovered,
        key=lambda item: (
            0 if item["category"] == "sector" else 1,
            item["group"].lower(),
            item["name"].lower(),
            item["ip"],
        ),
    )


def _sector_labels_by_vendor_and_ip() -> dict[tuple[str, str], dict]:
    db = get_db()
    rows = db.execute(
        """
        SELECT vendor, sector_ip, NULLIF(TRIM(sector_name), '') AS sector_name, COUNT(*) AS row_count
        FROM devices
        WHERE sector_ip IS NOT NULL AND sector_ip != ''
        GROUP BY vendor, sector_ip, NULLIF(TRIM(sector_name), '')
        """
    ).fetchall()
    target_rows = db.execute(
        """
        SELECT vendor, sector_ip, NULLIF(TRIM(sector_name), '') AS sector_name, source_detail, last_seen_at
        FROM sector_targets
        WHERE sector_ip IS NOT NULL AND sector_ip != ''
        """
    ).fetchall()

    labels_by_target: dict[tuple[str, str], dict] = defaultdict(
        lambda: {"device_count": 0, "sector_name": None, "source_detail": None, "_candidates": defaultdict(int)}
    )
    for row in rows:
        key = (row["vendor"], row["sector_ip"])
        label_data = labels_by_target[key]
        label_data["device_count"] += row["row_count"]

        cleaned_name = _clean_sector_name(row["sector_name"])
        if cleaned_name:
            label_data["_candidates"][cleaned_name] += row["row_count"]

    for row in target_rows:
        key = (row["vendor"], row["sector_ip"])
        label_data = labels_by_target[key]
        cleaned_name = _clean_sector_name(row["sector_name"])
        if cleaned_name:
            label_data["sector_name"] = cleaned_name
        if row["source_detail"]:
            label_data["source_detail"] = row["source_detail"]

    resolved: dict[tuple[str, str], dict] = {}
    for key, label_data in labels_by_target.items():
        candidates = label_data.pop("_candidates")
        if not label_data["sector_name"] and candidates:
            label_data["sector_name"] = sorted(candidates.items(), key=lambda item: (-item[1], item[0].lower()))[0][0]
        resolved[key] = {
            "device_count": label_data["device_count"],
            "sector_name": label_data["sector_name"],
            "source_detail": label_data["source_detail"],
        }
    return resolved


def _clean_sector_name(value: str | None) -> str | None:
    cleaned = " ".join((value or "").strip().split())
    if not cleaned or GENERIC_TARGET_LABEL_RE.match(cleaned):
        return None
    return cleaned


def _configured_target_name(value: str | None) -> str | None:
    cleaned = " ".join((value or "").strip().split())
    return cleaned or None


def _fallback_target_label(vendor: str, ip: str) -> str:
    return f"{vendor.title()} sector {ip}"


def _probe_target(target: dict, config: dict, last_success_at: str | None) -> dict:
    checked_at = utcnow_iso()
    ping_count = max(1, int(config["MONITOR_PING_COUNT"]))
    timeout_ms = max(250, int(config["MONITOR_PING_TIMEOUT_MS"]))
    retry_delay = max(0, int(config["MONITOR_RETRY_DELAY_SECONDS"]))

    primary = _run_ping(target["ip"], ping_count, timeout_ms)
    retry = None
    if primary["state"] == "offline" and retry_delay:
        time.sleep(retry_delay)
        retry = _run_ping(target["ip"], ping_count, timeout_ms)

    final_attempt = retry or primary
    result = {
        **target,
        "checked_at": checked_at,
        "last_success_at": last_success_at,
        "retry_performed": retry is not None,
        "attempts": [primary] + ([retry] if retry else []),
        "packets_sent": final_attempt["sent"],
        "packets_received": final_attempt["received"],
        "packet_loss_percent": final_attempt["loss_percent"],
        "avg_latency_ms": final_attempt["avg_latency_ms"],
        "probe_message": final_attempt["message"],
    }

    if final_attempt["state"] == "error":
        result["status"] = "unknown"
        result["status_label"] = "Unavailable"
    elif primary["state"] == "online" and not retry:
        result["status"] = "online"
        result["status_label"] = "Online"
        result["last_success_at"] = checked_at
    elif primary["state"] == "degraded":
        result["status"] = "degraded"
        result["status_label"] = "Packet loss"
        result["last_success_at"] = checked_at
    elif retry and retry["state"] in {"online", "degraded"}:
        result["status"] = "degraded"
        result["status_label"] = "Recovered on retry"
        result["last_success_at"] = checked_at
    elif final_attempt["state"] == "degraded":
        result["status"] = "degraded"
        result["status_label"] = "Degraded"
        result["last_success_at"] = checked_at
    else:
        result["status"] = "offline"
        result["status_label"] = "Offline"

    return result


def _run_ping(ip: str, count: int, timeout_ms: int) -> dict:
    command = _ping_command(ip, count, timeout_ms)
    timeout_seconds = max(5, count * max(timeout_ms / 1000, 1) + 5)

    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout_seconds,
        )
    except FileNotFoundError:
        return {
            "phase": "ping",
            "state": "error",
            "sent": count,
            "received": 0,
            "loss_percent": 100,
            "avg_latency_ms": None,
            "message": "The ping command is not available on this host.",
        }
    except subprocess.TimeoutExpired:
        return {
            "phase": "ping",
            "state": "offline",
            "sent": count,
            "received": 0,
            "loss_percent": 100,
            "avg_latency_ms": None,
            "message": f"No replies within the {count}-probe window.",
        }

    stdout = completed.stdout or ""
    stderr = completed.stderr or ""
    summary = _parse_ping_output(stdout, count)
    if summary is None:
        return {
            "phase": "ping",
            "state": "error",
            "sent": count,
            "received": 0,
            "loss_percent": 100,
            "avg_latency_ms": None,
            "message": (stderr.strip() or "Ping output could not be parsed.")[:180],
        }

    received = summary["received"]
    loss_percent = summary["loss_percent"]
    avg_latency_ms = summary["avg_latency_ms"]
    if received == 0:
        state = "offline"
        message = f"0/{count} replies"
    elif loss_percent > 0:
        state = "degraded"
        message = f"{received}/{count} replies with {loss_percent:.0f}% loss"
    else:
        state = "online"
        if avg_latency_ms is None:
            message = f"{received}/{count} replies"
        else:
            message = f"{received}/{count} replies, average {avg_latency_ms:.1f} ms"

    return {
        "phase": "ping",
        "state": state,
        "sent": count,
        "received": received,
        "loss_percent": loss_percent,
        "avg_latency_ms": avg_latency_ms,
        "message": message,
    }


def _ping_command(ip: str, count: int, timeout_ms: int) -> list[str]:
    if platform.system().lower().startswith("win"):
        return ["ping", "-n", str(count), "-w", str(timeout_ms), ip]
    timeout_seconds = max(1, int(round(timeout_ms / 1000)))
    return ["ping", "-c", str(count), "-W", str(timeout_seconds), ip]


def _parse_ping_output(output: str, count: int) -> dict | None:
    received_match = WINDOWS_RECEIVED_RE.search(output)
    if received_match:
        received = int(received_match.group(1))
        lost_match = WINDOWS_LOST_RE.search(output)
        avg_match = WINDOWS_AVG_RE.search(output)
        lost = int(lost_match.group(1)) if lost_match else max(0, count - received)
        return {
            "received": received,
            "loss_percent": (lost / count) * 100 if count else 100,
            "avg_latency_ms": float(avg_match.group(1)) if avg_match else None,
        }

    packet_match = POSIX_PACKET_RE.search(output)
    if not packet_match:
        return None

    sent = int(packet_match.group(1))
    received = int(packet_match.group(2))
    loss_match = POSIX_LOSS_RE.search(output)
    avg_match = POSIX_AVG_RE.search(output)
    if loss_match:
        loss_percent = float(loss_match.group(1))
    elif sent:
        loss_percent = ((sent - received) / sent) * 100
    else:
        loss_percent = 100
    return {
        "received": received,
        "loss_percent": loss_percent,
        "avg_latency_ms": float(avg_match.group(1)) if avg_match else None,
    }


def summarize_snapshot(results: list[dict]) -> dict:
    summary = {
        "total": len(results),
        "online": 0,
        "degraded": 0,
        "offline": 0,
        "unknown": 0,
        "sectors": 0,
        "switches": 0,
    }
    for item in results:
        summary[item["status"]] = summary.get(item["status"], 0) + 1
        if item["category"] == "sector":
            summary["sectors"] += 1
        elif item["category"] == "switch":
            summary["switches"] += 1
    return summary


class MonitoringService:
    def __init__(self, app):
        self.app = app
        self._lock = threading.Lock()
        self._wake_event = threading.Event()
        self._last_success_by_target: dict[str, str] = {}
        self._thread: threading.Thread | None = None
        self._snapshot = self._empty_snapshot()

    def start(self) -> None:
        if self._thread is not None or not self.app.config.get("MONITORING_ENABLED", True):
            return
        self._thread = threading.Thread(target=self._run_loop, name="monitoring-service", daemon=True)
        self._thread.start()
        self.request_refresh()

    def request_refresh(self) -> None:
        self._wake_event.set()

    def get_snapshot(self) -> dict:
        with self._lock:
            return copy.deepcopy(self._snapshot)

    def refresh_once(self) -> dict:
        with self.app.app_context():
            targets = build_monitor_targets(self.app)
            checked_at = utcnow_iso()
            if not targets:
                snapshot = self._empty_snapshot()
                snapshot["checked_at"] = checked_at
                snapshot["next_refresh_at"] = utcnow_iso()
            else:
                max_workers = min(max(1, int(self.app.config["MONITOR_MAX_WORKERS"])), len(targets))
                results: list[dict] = []
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    futures = {
                        executor.submit(
                            _probe_target,
                            target,
                            self.app.config,
                            self._last_success_by_target.get(target["target_id"]),
                        ): target["target_id"]
                        for target in targets
                    }
                    targets_by_id = {target["target_id"]: target for target in targets}
                    for future in as_completed(futures):
                        target_id = futures[future]
                        try:
                            result = future.result()
                        except Exception:
                            target = targets_by_id[target_id]
                            self.app.logger.exception("Monitoring probe failed for %s", target["ip"])
                            result = {
                                **target,
                                "checked_at": checked_at,
                                "last_success_at": self._last_success_by_target.get(target_id),
                                "retry_performed": False,
                                "attempts": [],
                                "packets_sent": int(self.app.config["MONITOR_PING_COUNT"]),
                                "packets_received": 0,
                                "packet_loss_percent": 100,
                                "avg_latency_ms": None,
                                "probe_message": "Probe failed before a result could be collected.",
                                "status": "unknown",
                                "status_label": "Unavailable",
                            }
                        if result.get("last_success_at"):
                            self._last_success_by_target[result["target_id"]] = result["last_success_at"]
                        results.append(result)

                results.sort(
                    key=lambda item: (
                        0 if item["category"] == "sector" else 1,
                        item["group"].lower(),
                        item["name"].lower(),
                        item["ip"],
                    )
                )
                refresh_seconds = max(5, int(self.app.config["MONITOR_REFRESH_SECONDS"]))
                next_refresh_at = (utcnow().timestamp() + refresh_seconds)
                snapshot = {
                    "checked_at": checked_at,
                    "next_refresh_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(next_refresh_at)),
                    "settings": {
                        "ping_count": int(self.app.config["MONITOR_PING_COUNT"]),
                        "refresh_seconds": refresh_seconds,
                        "retry_delay_seconds": int(self.app.config["MONITOR_RETRY_DELAY_SECONDS"]),
                    },
                    "summary": summarize_snapshot(results),
                    "groups": {
                        "sectors": [item for item in results if item["category"] == "sector"],
                        "switches": [item for item in results if item["category"] == "switch"],
                    },
                }

        with self._lock:
            self._snapshot = snapshot
            return copy.deepcopy(snapshot)

    def _run_loop(self) -> None:
        refresh_seconds = max(5, int(self.app.config["MONITOR_REFRESH_SECONDS"]))
        while True:
            self._wake_event.clear()
            try:
                self.refresh_once()
            except Exception:
                self.app.logger.exception("Monitoring refresh failed.")
            self._wake_event.wait(timeout=refresh_seconds)

    def _empty_snapshot(self) -> dict:
        return {
            "checked_at": None,
            "next_refresh_at": None,
            "settings": {
                "ping_count": int(self.app.config.get("MONITOR_PING_COUNT", 4)),
                "refresh_seconds": int(self.app.config.get("MONITOR_REFRESH_SECONDS", 30)),
                "retry_delay_seconds": int(self.app.config.get("MONITOR_RETRY_DELAY_SECONDS", 10)),
            },
            "summary": {
                "total": 0,
                "online": 0,
                "degraded": 0,
                "offline": 0,
                "unknown": 0,
                "sectors": 0,
                "switches": 0,
            },
            "groups": {
                "sectors": [],
                "switches": [],
            },
        }
