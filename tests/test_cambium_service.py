import asyncio
import unittest
from unittest.mock import patch

from app.services import cambium_service


class _FakeRoleTarget:
    async def click(self):
        return None


class _FakeMouse:
    async def wheel(self, _x, _y):
        return None


class _FakeTextLocator:
    def __init__(self, count=0, text=""):
        self._count = count
        self._text = text

    @property
    def first(self):
        return self

    async def count(self):
        return self._count

    async def inner_text(self, timeout=None):
        return self._text

    async def all(self):
        return []


class _FakePage:
    def __init__(self, *, title_text="", body_text=""):
        self._title_text = title_text
        self._body_text = body_text
        self.mouse = _FakeMouse()

    async def goto(self, _url, timeout=None):
        return None

    async def wait_for_timeout(self, _ms):
        return None

    async def wait_for_selector(self, _selector, timeout=None):
        return None

    async def title(self):
        return self._title_text

    def get_by_role(self, _role, name=None):
        return _FakeRoleTarget()

    def locator(self, selector):
        if selector == "body":
            return _FakeTextLocator(count=1, text=self._body_text)
        if selector == ".slick-row":
            return _FakeTextLocator(count=0)
        return _FakeTextLocator(count=0)


class _FakeContext:
    def __init__(self, page):
        self.page = page
        self.closed = False

    async def new_page(self):
        return self.page

    async def close(self):
        self.closed = True


class _FakeBrowser:
    def __init__(self, page):
        self.page = page
        self.contexts = []

    async def new_context(self):
        context = _FakeContext(self.page)
        self.contexts.append(context)
        return context


class CambiumServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_extract_device_label_cleans_cambium_title_suffix(self):
        page = _FakePage(title_text="West Tower AP - Cambium Networks")

        label = await cambium_service._extract_device_label(page, "10.0.0.20")

        self.assertEqual(label, "West Tower AP")

    async def test_scrape_device_keeps_sector_target_when_no_subscribers_exist(self):
        page = _FakePage(body_text="System Name: West Tower AP")
        browser = _FakeBrowser(page)

        with patch("app.services.cambium_service._smart_login", return_value=True):
            with patch("app.services.cambium_service._wait_for_wireless_grid", return_value=None):
                result = await cambium_service._scrape_device(
                    browser,
                    "10.0.0.20",
                    "user",
                    "pass",
                    asyncio.Semaphore(1),
                )

        self.assertEqual(result["devices"], [])
        self.assertEqual(result["sector_target"]["sector_name"], "West Tower AP")
        self.assertEqual(result["sector_target"]["sector_ip"], "10.0.0.20")
        self.assertTrue(browser.contexts[0].closed)


if __name__ == "__main__":
    unittest.main()
