import unittest
from unittest.mock import patch

from app.services import ubiquiti_service


class _FakePage:
    pass


class _FakeContext:
    def __init__(self, page):
        self.page = page
        self.closed = False

    def new_page(self):
        return self.page

    def close(self):
        self.closed = True


class _FakeBrowser:
    def __init__(self):
        self.contexts = []
        self.closed = False

    def new_context(self):
        context = _FakeContext(_FakePage())
        self.contexts.append(context)
        return context

    def close(self):
        self.closed = True


class _FakeChromium:
    def __init__(self, browser):
        self.browser = browser

    def launch(self, headless):
        return self.browser


class _FakePlaywrightManager:
    def __init__(self, browser):
        self.chromium = _FakeChromium(browser)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class UbiquitiServiceTests(unittest.TestCase):
    def test_run_scan_uses_fresh_browser_context_for_each_target(self):
        browser = _FakeBrowser()
        seen_pages = []

        def fake_scrape_device(browser, ip, username, password):
            context = browser.new_context()
            page = context.new_page()
            seen_pages.append((ip, id(page)))
            context.close()
            return {
                "devices": [
                    {
                        "mac": f"00:11:22:33:44:{ip.split('.')[-1]}",
                        "username": f"user-{ip}",
                        "sector_name": f"Sector {ip}",
                        "sector_ip": ip,
                        "source_ip": ip,
                        "timestamp": "2026-04-25T10:00:00Z",
                    }
                ],
                "sector_target": {
                    "sector_name": f"Sector {ip}",
                    "sector_ip": ip,
                    "source_detail": "Ubiquiti dashboard",
                    "timestamp": "2026-04-25T10:00:00Z",
                },
            }

        with patch("app.services.ubiquiti_service._sync_playwright", return_value=_FakePlaywrightManager(browser)):
            with patch("app.services.ubiquiti_service._scrape_device", side_effect=fake_scrape_device):
                result = ubiquiti_service.run_scan(
                    {
                        "UBIQUITI_USERNAME": "user",
                        "UBIQUITI_PASSWORD": "pass",
                        "PLAYWRIGHT_HEADLESS": True,
                    },
                    ["10.0.0.5", "10.0.0.6"],
                )

        self.assertEqual(result.attempted_targets, 2)
        self.assertEqual(result.successful_targets, 2)
        self.assertEqual(len(result.devices), 2)
        self.assertEqual(len(result.sector_targets), 2)
        self.assertEqual(len(browser.contexts), 2)
        self.assertNotEqual(seen_pages[0][1], seen_pages[1][1])
        self.assertTrue(all(context.closed for context in browser.contexts))
        self.assertTrue(browser.closed)


if __name__ == "__main__":
    unittest.main()
