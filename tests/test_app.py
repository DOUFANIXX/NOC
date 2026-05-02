import shutil
import unittest
from pathlib import Path
from unittest.mock import patch

from app import create_app
from app.services.user_service import create_user, get_user_by_username


TEST_ROOT = Path(".tmp-tests")


class AppFactoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        TEST_ROOT.mkdir(exist_ok=True)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(TEST_ROOT, ignore_errors=True)

    def setUp(self):
        self.temp_dir = TEST_ROOT / self._testMethodName
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        instance_path = self.temp_dir
        self.app = create_app(
            {
                "TESTING": True,
                "INSTANCE_PATH": instance_path,
                "DATABASE_PATH": instance_path / "test.sqlite3",
                "LOG_DIR": instance_path / "logs",
                "SECRET_KEY": "test-secret",
                "BOOTSTRAP_ADMIN_PASSWORD": "StrongPass123",
                "SCAN_TARGETS_FILE": Path("config/scan_targets.json"),
                "SWITCH_INVENTORY_SEED_FILE": Path("config/switch_inventory.seed.json"),
                "HT_SWITCH_INVENTORY_SEED_FILE": Path("config/ht_switch_inventory.seed.json"),
            }
        )
        self.client = self.app.test_client()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _login_as_bootstrap_admin(self):
        with self.client.session_transaction() as session:
            session["user_id"] = 1
            session["role"] = "admin"
            session["_csrf_token"] = "test-csrf"

    def _create_user(self, username: str, password: str, role: str = "viewer", ui_preference: str = "dark") -> int:
        with self.app.app_context():
            return create_user(username, password, role, ui_preference)

    def _login_as_user(self, user_id: int, role: str):
        with self.client.session_transaction() as session:
            session["user_id"] = user_id
            session["role"] = role
            session["_csrf_token"] = "test-csrf"

    def _csrf_token(self):
        with self.client.session_transaction() as session:
            token = session.get("_csrf_token") or "test-csrf"
            session["_csrf_token"] = token
            return token

    def test_healthcheck(self):
        response = self.client.get("/healthz")
        self.assertEqual(response.status_code, 200)
        self.assertIn("ok", response.get_data(as_text=True))

    def test_readiness_check(self):
        response = self.client.get("/readyz")
        self.assertEqual(response.status_code, 200)
        self.assertIn("ready", response.get_data(as_text=True))

    def test_login_page_loads(self):
        response = self.client.get("/auth/login")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Network Operations Console", response.get_data(as_text=True))

    def test_audit_page_loads_for_authenticated_user(self):
        self._login_as_bootstrap_admin()
        response = self.client.get("/audit/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Audit Log", response.get_data(as_text=True))

    def test_settings_page_loads_for_authenticated_user(self):
        self._login_as_bootstrap_admin()
        response = self.client.get("/settings/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Settings and Control", response.get_data(as_text=True))

    def test_jobs_page_loads_for_authenticated_user(self):
        self._login_as_bootstrap_admin()
        response = self.client.get("/jobs/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Background Jobs", response.get_data(as_text=True))

    def test_monitoring_page_loads_for_authenticated_user(self):
        self._login_as_bootstrap_admin()

        class FakeMonitoringService:
            def request_refresh(self):
                return None

            def get_snapshot(self):
                return {
                    "checked_at": "2026-04-24T12:00:00Z",
                    "next_refresh_at": "2026-04-24T12:00:30Z",
                    "settings": {
                        "ping_count": 4,
                        "refresh_seconds": 30,
                        "retry_delay_seconds": 10,
                    },
                    "summary": {
                        "total": 2,
                        "online": 1,
                        "degraded": 1,
                        "offline": 0,
                        "unknown": 0,
                        "sectors": 1,
                        "switches": 1,
                    },
                    "groups": {
                        "sectors": [
                            {
                                "name": "Sector Alpha",
                                "group": "Cambium",
                                "ip": "10.0.0.10",
                                "status": "online",
                                "status_label": "Online",
                                "probe_message": "4/4 replies, average 2.0 ms",
                                "packets_received": 4,
                                "packets_sent": 4,
                                "packet_loss_percent": 0,
                                "avg_latency_ms": 2.0,
                                "retry_performed": False,
                                "last_success_at": "2026-04-24T12:00:00Z",
                            }
                        ],
                        "switches": [
                            {
                                "name": "SW-CORE-01",
                                "group": "ULTRA",
                                "ip": "10.0.1.1",
                                "detail": "HQ, Core",
                                "status": "degraded",
                                "status_label": "Recovered on retry",
                                "probe_message": "4/4 replies, average 5.0 ms",
                                "packets_received": 4,
                                "packets_sent": 4,
                                "packet_loss_percent": 0,
                                "avg_latency_ms": 5.0,
                                "retry_performed": True,
                                "last_success_at": "2026-04-24T12:00:00Z",
                            }
                        ],
                    },
                }

        self.app.extensions["monitoring_service"] = FakeMonitoringService()

        response = self.client.get("/monitoring/")
        body = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("Sector and Switch Monitoring", body)
        self.assertIn("Sector Alpha", body)
        self.assertIn("SW-CORE-01", body)

    def test_monitoring_page_shows_offline_priority_lists(self):
        self._login_as_bootstrap_admin()

        class FakeMonitoringService:
            def request_refresh(self):
                return None

            def get_snapshot(self):
                return {
                    "checked_at": "2026-04-24T12:00:00Z",
                    "next_refresh_at": "2026-04-24T12:00:30Z",
                    "settings": {
                        "ping_count": 4,
                        "refresh_seconds": 30,
                        "retry_delay_seconds": 10,
                    },
                    "summary": {
                        "total": 2,
                        "online": 0,
                        "degraded": 0,
                        "offline": 2,
                        "unknown": 0,
                        "sectors": 1,
                        "switches": 1,
                    },
                    "groups": {
                        "sectors": [
                            {
                                "name": "Sector Offline",
                                "group": "Cambium",
                                "ip": "10.0.0.10",
                                "detail": "Configured scan target",
                                "status": "offline",
                                "status_label": "Offline",
                                "probe_message": "0/4 replies",
                                "packets_received": 0,
                                "packets_sent": 4,
                                "packet_loss_percent": 100,
                                "avg_latency_ms": None,
                                "retry_performed": True,
                                "last_success_at": "2026-04-24T10:00:00Z",
                            }
                        ],
                        "switches": [
                            {
                                "name": "SW-OFFLINE-01",
                                "group": "ULTRA",
                                "ip": "10.0.1.1",
                                "detail": "HQ, Core",
                                "status": "offline",
                                "status_label": "Offline",
                                "probe_message": "0/4 replies",
                                "packets_received": 0,
                                "packets_sent": 4,
                                "packet_loss_percent": 100,
                                "avg_latency_ms": None,
                                "retry_performed": True,
                                "last_success_at": "2026-04-24T09:00:00Z",
                            }
                        ],
                    },
                }

        self.app.extensions["monitoring_service"] = FakeMonitoringService()

        response = self.client.get("/monitoring/")
        body = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("Offline sectors", body)
        self.assertIn("Offline switches", body)
        self.assertIn("Sector Offline", body)
        self.assertIn("SW-OFFLINE-01", body)

    def test_monitoring_nav_appears_before_dashboard(self):
        self._login_as_bootstrap_admin()

        class FakeMonitoringService:
            def request_refresh(self):
                return None

            def get_snapshot(self):
                return {
                    "checked_at": None,
                    "next_refresh_at": None,
                    "settings": {
                        "ping_count": 4,
                        "refresh_seconds": 30,
                        "retry_delay_seconds": 10,
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
                    "groups": {"sectors": [], "switches": []},
                }

        self.app.extensions["monitoring_service"] = FakeMonitoringService()

        response = self.client.get("/monitoring/")
        body = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertLess(body.index("Monitoring"), body.index("Dashboard"))

    def test_monitoring_page_paginates_sector_cards(self):
        self._login_as_bootstrap_admin()

        class FakeMonitoringService:
            def request_refresh(self):
                return None

            def get_snapshot(self):
                sectors = []
                for index in range(1, 22):
                    sectors.append(
                        {
                            "name": f"Sector {index:02d}",
                            "group": "Ubiquiti",
                            "ip": f"10.0.0.{index}",
                            "detail": "Configured scan target",
                            "status": "online",
                            "status_label": "Online",
                            "probe_message": "4/4 replies, average 2.0 ms",
                            "packets_received": 4,
                            "packets_sent": 4,
                            "packet_loss_percent": 0,
                            "avg_latency_ms": 2.0,
                            "retry_performed": False,
                            "last_success_at": "2026-04-24T12:00:00Z",
                        }
                    )
                return {
                    "checked_at": "2026-04-24T12:00:00Z",
                    "next_refresh_at": "2026-04-24T12:00:30Z",
                    "settings": {
                        "ping_count": 4,
                        "refresh_seconds": 30,
                        "retry_delay_seconds": 10,
                    },
                    "summary": {
                        "total": 21,
                        "online": 21,
                        "degraded": 0,
                        "offline": 0,
                        "unknown": 0,
                        "sectors": 21,
                        "switches": 0,
                    },
                    "groups": {
                        "sectors": sectors,
                        "switches": [],
                    },
                }

        self.app.extensions["monitoring_service"] = FakeMonitoringService()

        response = self.client.get("/monitoring/?sectors_page=2")
        body = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("Sector 21", body)
        self.assertNotIn("Sector 01", body)
        self.assertIn("Showing 21-21 of 21", body)

    def test_inventory_page_shows_restart_action_while_scan_is_running(self):
        self._login_as_bootstrap_admin()
        with patch(
            "app.routes.inventory.scan_readiness",
            return_value={
                "vendor": "ubiquiti",
                "ready": False,
                "running": True,
                "restartable": True,
                "reason": "A ubiquiti scan is already queued or running.",
                "targets": 1,
                "credentials_configured": True,
            },
        ):
            response = self.client.get("/inventory/ubiquiti")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Restart Ubiquiti Scan", response.get_data(as_text=True))

    def test_restart_scan_route_queues_replacement_job(self):
        self._login_as_bootstrap_admin()

        class FakeJobManager:
            def __init__(self):
                self.calls = []

            def restart_scan(self, vendor, requested_by, trigger_source):
                self.calls.append((vendor, requested_by, trigger_source))
                return 42, [7]

        fake_manager = FakeJobManager()
        self.app.extensions["job_manager"] = fake_manager

        with patch(
            "app.routes.inventory.scan_readiness",
            return_value={
                "vendor": "ubiquiti",
                "ready": False,
                "running": True,
                "restartable": True,
                "reason": "A ubiquiti scan is already queued or running.",
                "targets": 1,
                "credentials_configured": True,
            },
        ):
            response = self.client.post(
                "/inventory/run/ubiquiti",
                data={"_csrf_token": self._csrf_token(), "action": "restart"},
                follow_redirects=True,
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(fake_manager.calls, [("ubiquiti", 1, "manual")])
        self.assertIn("Ubiquiti restart queued as job #42. Replacing #7.", response.get_data(as_text=True))

    def test_viewer_can_open_inventory_but_cannot_run_scan(self):
        viewer_id = self._create_user("viewer1", "StrongPass123", "viewer")
        self._login_as_user(viewer_id, "viewer")

        response = self.client.get("/inventory/cambium")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Viewer only", response.get_data(as_text=True))

        blocked = self.client.post(
            "/inventory/run/cambium",
            data={"_csrf_token": self._csrf_token()},
        )
        self.assertEqual(blocked.status_code, 403)

    def test_viewer_navigation_only_shows_allowed_sections(self):
        viewer_id = self._create_user("viewer-nav", "StrongPass123", "viewer")
        self._login_as_user(viewer_id, "viewer")

        class FakeMonitoringService:
            def request_refresh(self):
                return None

            def get_snapshot(self):
                return {
                    "checked_at": None,
                    "next_refresh_at": None,
                    "settings": {
                        "ping_count": 4,
                        "refresh_seconds": 30,
                        "retry_delay_seconds": 10,
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
                    "groups": {"sectors": [], "switches": []},
                }

        self.app.extensions["monitoring_service"] = FakeMonitoringService()
        response = self.client.get("/monitoring/")
        body = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("Monitoring", body)
        self.assertIn("Cambium Inventory", body)
        self.assertIn("Ubiquiti Inventory", body)
        self.assertIn("Switch Inspection", body)
        self.assertNotIn("Dashboard", body)
        self.assertNotIn("Jobs", body)
        self.assertNotIn("Audit Log", body)
        self.assertNotIn("Settings", body)

    def test_viewer_is_redirected_to_monitoring_after_login(self):
        self._create_user("viewer-login", "StrongPass123", "viewer")
        token = self._csrf_token()

        response = self.client.post(
            "/auth/login",
            data={"_csrf_token": token, "username": "viewer-login", "password": "StrongPass123"},
            follow_redirects=False,
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers["Location"].endswith("/monitoring/"))

    def test_light_theme_preference_renders_same_shell_with_light_theme(self):
        user_id = self._create_user("viewer-light", "StrongPass123", "viewer", "light")
        self._login_as_user(user_id, "viewer")

        class FakeMonitoringService:
            def request_refresh(self):
                return None

            def get_snapshot(self):
                return {
                    "checked_at": None,
                    "next_refresh_at": None,
                    "settings": {
                        "ping_count": 4,
                        "refresh_seconds": 30,
                        "retry_delay_seconds": 10,
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
                    "groups": {"sectors": [], "switches": []},
                }

        self.app.extensions["monitoring_service"] = FakeMonitoringService()
        response = self.client.get("/monitoring/")

        self.assertEqual(response.status_code, 200)
        self.assertIn('data-theme="light"', response.get_data(as_text=True))
        self.assertIn("Vigilant System", response.get_data(as_text=True))
        self.assertNotIn("Classic Console", response.get_data(as_text=True))

    def test_user_can_update_theme_from_shell(self):
        user_id = self._create_user("viewer-theme", "StrongPass123", "viewer", "dark")
        self._login_as_user(user_id, "viewer")

        response = self.client.post(
            "/auth/ui-mode",
            data={
                "_csrf_token": self._csrf_token(),
                "ui_preference": "light",
                "next_path": "/monitoring/",
            },
            follow_redirects=False,
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers["Location"].endswith("/monitoring/"))
        with self.app.app_context():
            user = get_user_by_username("viewer-theme")
            self.assertEqual(user["ui_preference"], "light")

    def test_viewer_cannot_access_operator_pages(self):
        viewer_id = self._create_user("viewer-locked", "StrongPass123", "viewer")
        self._login_as_user(viewer_id, "viewer")

        self.assertEqual(self.client.get("/").status_code, 403)
        self.assertEqual(self.client.get("/jobs/").status_code, 403)
        self.assertEqual(self.client.get("/audit/").status_code, 403)
        self.assertEqual(self.client.get("/settings/").status_code, 403)

    def test_viewer_can_open_switch_inspection_but_not_admin_switch_inventory(self):
        viewer_id = self._create_user("viewer2", "StrongPass123", "viewer")
        self._login_as_user(viewer_id, "viewer")

        response = self.client.get("/switches/ultra")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Switch Port Inspection", response.get_data(as_text=True))

        blocked = self.client.get("/admin/switches")
        self.assertEqual(blocked.status_code, 403)

    def test_switch_inspection_renders_na_speed_for_down_ports(self):
        self._login_as_bootstrap_admin()

        with self.app.app_context():
            switch_id = 1

        with patch(
            "app.routes.switches.inspect_described_ports",
            return_value=[
                {
                    "port": "GE1/0/1",
                    "status": "DOWN",
                    "speed": "1000",
                    "description": "9500220-AP1",
                }
            ],
        ):
            response = self.client.get(f"/switches/ultra?switch_id={switch_id}")

        body = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("GE1/0/1", body)
        self.assertIn("N/A", body)

    def test_admin_can_create_viewer_user_from_gui(self):
        self._login_as_bootstrap_admin()

        response = self.client.post(
            "/admin/users",
            data={
                "_csrf_token": self._csrf_token(),
                "action": "create",
                "username": "viewer-gui",
                "role": "viewer",
                "password": "StrongPass123",
            },
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("User created.", response.get_data(as_text=True))
        with self.app.app_context():
            user = get_user_by_username("viewer-gui")
            self.assertIsNotNone(user)
            self.assertEqual(user["role"], "viewer")
            self.assertEqual(user["ui_preference"], "dark")

    def test_operator_can_manage_daily_scan_schedule(self):
        operator_id = self._create_user("operator1", "StrongPass123", "operator")
        self._login_as_user(operator_id, "operator")

        response = self.client.post(
            "/jobs/schedule",
            data={
                "_csrf_token": self._csrf_token(),
                "vendor": "cambium",
                "enabled": "on",
                "daily_time": "01:30",
            },
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("Schedule updated.", response.get_data(as_text=True))
        self.assertIn("01:30", response.get_data(as_text=True))

    def test_viewer_cannot_access_daily_scan_schedule(self):
        viewer_id = self._create_user("viewer3", "StrongPass123", "viewer")
        self._login_as_user(viewer_id, "viewer")

        response = self.client.get("/jobs/schedule")
        self.assertEqual(response.status_code, 403)


if __name__ == "__main__":
    unittest.main()
