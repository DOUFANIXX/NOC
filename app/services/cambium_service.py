from __future__ import annotations

import asyncio
import logging
import re

from app.models.schemas import ScanExecutionResult
from app.utils.helpers import utcnow_iso


logger = logging.getLogger(__name__)
TITLE_SUFFIX_RE = re.compile(r"\s*[-|]\s*Cambium.*$", re.IGNORECASE)
LABELED_VALUE_RE = re.compile(
    r"(?im)^\s*(?:device\s+name|ap\s+name|radio\s+name|system\s+name|host\s+name|hostname)\s*[:\-]?\s*(.+?)\s*$"
)
IGNORED_SECTOR_LABELS = {"login", "overview", "dashboard", "unknown"}


def normalize_mac(mac: str | None) -> str | None:
    return mac.replace("-", ":").lower() if mac else None


def _fallback_sector_name(ip: str) -> str:
    return f"Cambium sector {ip}"


def _clean_sector_name(value: str | None, ip: str) -> str:
    cleaned = " ".join((value or "").strip().split())
    if not cleaned:
        return _fallback_sector_name(ip)
    cleaned = TITLE_SUFFIX_RE.sub("", cleaned).strip(" -|")
    if not cleaned or cleaned.lower() in IGNORED_SECTOR_LABELS:
        return _fallback_sector_name(ip)
    return cleaned


def _compose_sector_name(configured_name: str | None, detected_name: str, ip: str) -> str:
    configured = " ".join((configured_name or "").strip().split())
    if configured:
        return configured
    return _clean_sector_name(detected_name, ip)


async def _extract_device_label(page, ip: str) -> str:
    fallback = _fallback_sector_name(ip)
    candidates = []

    try:
        candidates.append(await page.title())
    except Exception:
        pass

    for selector in (
        ".navbar-text.device-name",
        ".device-name",
        ".deviceName",
        ".systemName",
        ".hostname",
        "[id*='host']",
        "[class*='host']",
        "[id*='device']",
        "[class*='device']",
    ):
        try:
            locator = page.locator(selector).first
            if await locator.count():
                candidates.append(await locator.inner_text())
        except Exception:
            continue

    try:
        body_text = await page.locator("body").inner_text(timeout=5000)
        labeled_match = LABELED_VALUE_RE.search(body_text)
        if labeled_match:
            candidates.append(labeled_match.group(1))
    except Exception:
        pass

    for candidate in candidates:
        cleaned = _clean_sector_name(candidate, ip)
        if cleaned != fallback:
            return cleaned
    return fallback


async def _wait_for_wireless_grid(page) -> None:
    for selector in (".slick-row", ".slick-viewport", ".slick-canvas", ".grid-canvas"):
        try:
            await page.wait_for_selector(selector, timeout=5000)
            return
        except Exception:
            continue
    await page.wait_for_timeout(1000)


async def _smart_login(page, username: str, password: str, ip: str) -> bool:
    try:
        await page.wait_for_selector("input", timeout=10000)
        try:
            if await page.get_by_role("textbox", name="Username").count() > 0:
                await page.get_by_role("textbox", name="Username").fill(username)
                if await page.locator("#login1").count() > 0:
                    await page.locator("#login1").click()
                    await page.wait_for_selector('input[type="password"]', timeout=5000)
                    await page.get_by_role("textbox", name="Password").fill(password)
                    await page.keyboard.press("Enter")
                    return True
        except Exception:
            pass

        try:
            if await page.locator('input[name="username"]').count() > 0:
                await page.locator('input[name="username"]').fill(username)
            if await page.locator('input[name="password"]').count() > 0:
                await page.locator('input[name="password"]').fill(password)
            if await page.locator('button[type="submit"]').count() > 0:
                await page.locator('button[type="submit"]').click()
            else:
                await page.keyboard.press("Enter")
            return True
        except Exception:
            pass

        await page.keyboard.press("Enter")
        return True
    except Exception as exc:
        logger.warning("Cambium login failed for %s: %s", ip, exc)
        return False


async def _scrape_device(browser, ip: str, username: str, password: str, semaphore: asyncio.Semaphore) -> dict:
    async with semaphore:
        context = await browser.new_context()
        page = await context.new_page()
        try:
            await page.goto(f"http://{ip}/", timeout=20000)
            await page.wait_for_timeout(1500)

            if not await _smart_login(page, username, password, ip):
                raise RuntimeError("Login failed")

            timestamp = utcnow_iso()
            sector_name = await _extract_device_label(page, ip)

            await page.get_by_role("link", name="M Monitor").click()
            await page.wait_for_timeout(500)
            await page.get_by_role("link", name="Wireless").click()
            await _wait_for_wireless_grid(page)

            rows_locator = page.locator(".slick-row")
            inventory = []

            if await rows_locator.count():
                await page.mouse.wheel(0, 10000)
                await page.wait_for_timeout(500)
                await page.mouse.wheel(0, -10000)
                await page.wait_for_timeout(500)

                rows = await rows_locator.all()
                for row in rows:
                    cells = [value.strip() for value in await row.locator(".slick-cell").all_inner_texts() if value.strip()]
                    if len(cells) < 5:
                        continue
                    try:
                        mac = normalize_mac(cells[0])
                        ip_addr = cells[1]
                        username_value = cells[2]
                        rssi = cells[5] if len(cells) > 5 else ""
                    except IndexError:
                        continue

                    device_type = ""
                    for cell in reversed(cells):
                        if any(marker in cell for marker in ("GHz", "Force", "ePMP", "LiteBeam", "NanoBeam")):
                            device_type = cell
                            break

                    inventory.append(
                        {
                            "mac": mac,
                            "username": username_value,
                            "ip": ip_addr,
                            "rssi": rssi,
                            "sector_name": sector_name,
                            "sector_ip": ip,
                            "source_ip": ip,
                            "device_type": device_type,
                            "firmware": "",
                            "timestamp": timestamp,
                        }
                    )
            return {
                "devices": inventory,
                "sector_target": {
                    "sector_name": sector_name,
                    "sector_ip": ip,
                    "source_detail": "Cambium dashboard",
                    "timestamp": timestamp,
                },
            }
        finally:
            await context.close()


async def _scrape_target(
    browser,
    target: dict,
    username: str,
    password: str,
    semaphore: asyncio.Semaphore,
) -> dict:
    ip = str(target.get("ip", "")).strip()
    configured_name = str(target.get("name", "")).strip()
    result = await _scrape_device(browser, ip, username, password, semaphore)

    if configured_name:
        for device in result.get("devices", []):
            device["sector_name"] = _compose_sector_name(configured_name, device.get("sector_name"), ip)
        sector_target = result.get("sector_target")
        if sector_target:
            sector_target["sector_name"] = _compose_sector_name(configured_name, sector_target.get("sector_name"), ip)

    return result


async def _run_async_scan(targets: list[dict], username: str, password: str, headless: bool) -> ScanExecutionResult:
    if not username or not password:
        raise RuntimeError("Cambium credentials are not configured.")

    semaphore = asyncio.Semaphore(8)
    async with _async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=headless)
        try:
            tasks = [
                _scrape_target(browser, target, username, password, semaphore)
                for target in targets
                if str(target.get("ip", "")).strip()
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)
        finally:
            await browser.close()

    flattened: list[dict] = []
    sector_targets: list[dict] = []
    failed_targets: list[dict] = []
    successful_targets = 0
    active_targets = [target for target in targets if str(target.get("ip", "")).strip()]
    for target, result in zip(active_targets, results):
        ip = str(target.get("ip", "")).strip()
        if isinstance(result, Exception):
            logger.warning("Cambium scan task failed for %s: %s", ip, result)
            failed_targets.append({"target": ip, "error": str(result)})
            continue
        successful_targets += 1
        flattened.extend(result.get("devices", []))
        if result.get("sector_target"):
            sector_targets.append(result["sector_target"])
    return ScanExecutionResult(
        devices=flattened,
        sector_targets=sector_targets,
        attempted_targets=len(active_targets),
        successful_targets=successful_targets,
        failed_targets=failed_targets,
    )


def run_scan(config: dict, targets: list[dict]) -> ScanExecutionResult:
    return asyncio.run(
        _run_async_scan(
            targets=targets,
            username=config["CAMBIUM_USERNAME"],
            password=config["CAMBIUM_PASSWORD"],
            headless=config["PLAYWRIGHT_HEADLESS"],
        )
    )


def _async_playwright():
    from playwright.async_api import async_playwright

    return async_playwright()
