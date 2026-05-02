from __future__ import annotations

import re
import time
from collections.abc import Callable

from app.models.schemas import ScanExecutionResult
from app.utils.helpers import utcnow_iso


class ScanAborted(RuntimeError):
    pass


GENERIC_SECTOR_LABEL_RE = re.compile(r"^ubiquiti\s+target\s+\d+$", re.IGNORECASE)
TITLE_SUFFIX_RE = re.compile(r"\s*[-|]\s*(?:airOS|airMAX|Ubiquiti.*)$", re.IGNORECASE)
LABELED_VALUE_RE = re.compile(
    r"(?im)^\s*(?:device\s+name|device\s+hostname|host\s+name|hostname|radio\s+name|system\s+name)\s*[:\-]?\s*(.+?)\s*$"
)
IGNORED_SECTOR_LABELS = {"login", "overview", "dashboard", "unknown"}


def _clean_sector_label(value: str | None) -> str | None:
    cleaned = " ".join((value or "").strip().split())
    if not cleaned or GENERIC_SECTOR_LABEL_RE.match(cleaned):
        return None
    cleaned = TITLE_SUFFIX_RE.sub("", cleaned).strip(" -|")
    if cleaned.lower() in IGNORED_SECTOR_LABELS:
        return None
    return cleaned or None


def _extract_device_label(page) -> str | None:
    candidates = []
    try:
        candidates.append(page.title())
    except Exception:
        pass

    for selector in (
        ".hostname",
        ".deviceName",
        ".device-name",
        "#deviceName",
        ".appName",
        ".systemName",
        "[id*='host']",
        "[class*='host']",
        "[id*='device']",
        "[class*='device']",
    ):
        try:
            locator = page.locator(selector).first
            if locator.count():
                candidates.append(locator.inner_text())
        except Exception:
            continue

    try:
        body_text = page.locator("body").inner_text(timeout=5000)
        labeled_match = LABELED_VALUE_RE.search(body_text)
        if labeled_match:
            candidates.append(labeled_match.group(1))
    except Exception:
        pass

    for candidate in candidates:
        cleaned = _clean_sector_label(candidate)
        if cleaned:
            return cleaned
    return None


def _scrape_device(browser, ip: str, username: str, password: str) -> dict:
    context = browser.new_context()
    page = context.new_page()
    try:
        page.goto(f"http://{ip}/", timeout=10000)
        page.get_by_role("textbox", name="Username").fill(username)
        page.get_by_role("textbox", name="Password").fill(password)
        page.get_by_role("button", name="Login").click()

        for selector in (".ui-widget-overlay", ".blockUI"):
            try:
                page.wait_for_selector(selector, state="detached", timeout=10000)
            except Exception:
                pass

        timestamp = utcnow_iso()
        device_label = _extract_device_label(page) or f"Ubiquiti sector {ip}"
        page.get_by_role("listitem").filter(has_text="Tools").get_by_role("img").click()
        page.get_by_role("link", name="Discovery").click()
        time.sleep(5)
        page.wait_for_selector(".dataTables_wrapper.no-footer table", timeout=10000)

        rows = page.locator(".dataTables_wrapper.no-footer table tbody tr")
        row_count = rows.count()
        results = []

        for row_index in range(row_count):
            cells = rows.nth(row_index).locator("td")
            values = []
            for cell_index in range(cells.count()):
                values.append(cells.nth(cell_index).inner_text().strip())
            if len(values) < 7:
                continue
            results.append(
                {
                    "mac": values[0],
                    "username": values[1],
                    "device_type": values[4],
                    "firmware": values[5],
                    "ip": values[6],
                    "rssi": "",
                    "sector_name": _clean_sector_label(values[3]) or device_label,
                    "sector_ip": ip,
                    "source_ip": ip,
                    "timestamp": timestamp,
                }
            )
        return {
            "devices": results,
            "sector_target": {
                "sector_name": device_label,
                "sector_ip": ip,
                "source_detail": "Ubiquiti dashboard",
                "timestamp": timestamp,
            },
        }
    finally:
        context.close()


def _sync_playwright():
    from playwright.sync_api import sync_playwright

    return sync_playwright()


def run_scan(
    config: dict,
    targets: list[str],
    should_abort: Callable[[], bool] | None = None,
) -> ScanExecutionResult:
    if not config["UBIQUITI_USERNAME"] or not config["UBIQUITI_PASSWORD"]:
        raise RuntimeError("Ubiquiti credentials are not configured.")

    all_results = []
    sector_targets: list[dict] = []
    failed_targets: list[dict] = []
    successful_targets = 0
    with _sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=config["PLAYWRIGHT_HEADLESS"])
        try:
            for ip in targets:
                if should_abort and should_abort():
                    raise ScanAborted("Ubiquiti scan was superseded by a newer request.")
                try:
                    scrape_result = _scrape_device(
                        browser=browser,
                        ip=ip,
                        username=config["UBIQUITI_USERNAME"],
                        password=config["UBIQUITI_PASSWORD"],
                    )
                    all_results.extend(scrape_result.get("devices", []))
                    if scrape_result.get("sector_target"):
                        sector_targets.append(scrape_result["sector_target"])
                    successful_targets += 1
                except Exception as exc:
                    failed_targets.append({"target": ip, "error": str(exc)})
                    continue
        finally:
            browser.close()
    return ScanExecutionResult(
        devices=all_results,
        sector_targets=sector_targets,
        attempted_targets=len(targets),
        successful_targets=successful_targets,
        failed_targets=failed_targets,
    )
