import json
import shutil
import unittest
from pathlib import Path

from app import create_app
from app.services.inventory_service import upsert_devices
from app.services.monitoring_service import build_monitor_targets
from app.services.sector_target_service import upsert_sector_targets


TEST_ROOT = Path(".tmp-tests-monitoring")


class MonitoringServiceTests(unittest.TestCase):
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
        self.scan_targets = self.temp_dir / "scan_targets.json"
        self.scan_targets.write_text(
            json.dumps(
                {
                    "cambium": [],
                    "ubiquiti": ["10.0.0.5", "10.0.0.6"],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        self.app = create_app(
            {
                "TESTING": True,
                "INSTANCE_PATH": self.temp_dir,
                "DATABASE_PATH": self.temp_dir / "test.sqlite3",
                "LOG_DIR": self.temp_dir / "logs",
                "SECRET_KEY": "test-secret",
                "BOOTSTRAP_ADMIN_PASSWORD": "StrongPass123",
                "SCAN_TARGETS_FILE": self.scan_targets,
                "SWITCH_INVENTORY_SEED_FILE": Path("config/switch_inventory.seed.json"),
                "HT_SWITCH_INVENTORY_SEED_FILE": Path("config/ht_switch_inventory.seed.json"),
            }
        )

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_monitoring_prefers_real_sector_name_over_generic_target_label(self):
        with self.app.app_context():
            upsert_devices(
                "ubiquiti",
                [
                    {
                        "mac": "00:11:22:33:44:55",
                        "username": "sub-a",
                        "sector_name": "Ubiquiti target 1",
                        "sector_ip": "10.0.0.5",
                        "timestamp": "2026-04-25T10:00:00Z",
                    },
                    {
                        "mac": "00:11:22:33:44:56",
                        "username": "sub-b",
                        "sector_name": "North Ring AP",
                        "sector_ip": "10.0.0.5",
                        "timestamp": "2026-04-25T10:00:00Z",
                    },
                    {
                        "mac": "00:11:22:33:44:57",
                        "username": "sub-c",
                        "sector_name": "North Ring AP",
                        "sector_ip": "10.0.0.5",
                        "timestamp": "2026-04-25T10:00:00Z",
                    },
                ],
            )

            targets = build_monitor_targets(self.app)

        ubiquiti_target = next(item for item in targets if item["ip"] == "10.0.0.5")
        self.assertEqual(ubiquiti_target["name"], "North Ring AP")
        self.assertEqual(ubiquiti_target["detail"], "3 subscriber records seen on latest inventory")

    def test_monitoring_uses_ip_fallback_when_only_generic_label_exists(self):
        with self.app.app_context():
            upsert_devices(
                "ubiquiti",
                [
                    {
                        "mac": "00:11:22:33:44:66",
                        "username": "sub-d",
                        "sector_name": "Ubiquiti target 2",
                        "sector_ip": "10.0.0.6",
                        "timestamp": "2026-04-25T10:00:00Z",
                    }
                ],
            )

            targets = build_monitor_targets(self.app)

        ubiquiti_target = next(item for item in targets if item["ip"] == "10.0.0.6")
        self.assertEqual(ubiquiti_target["name"], "Ubiquiti sector 10.0.0.6")
        self.assertEqual(ubiquiti_target["detail"], "1 subscriber records seen on latest inventory")

    def test_monitoring_uses_configured_target_name_when_inventory_is_missing(self):
        self.scan_targets.write_text(
            json.dumps(
                {
                    "cambium": [{"ip": "10.0.0.20", "name": "Cambium West Sector"}],
                    "ubiquiti": [{"ip": "10.0.0.21", "name": "Ubiquiti North Sector"}],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        with self.app.app_context():
            targets = build_monitor_targets(self.app)

        cambium_target = next(item for item in targets if item["ip"] == "10.0.0.20")
        ubiquiti_target = next(item for item in targets if item["ip"] == "10.0.0.21")
        self.assertEqual(cambium_target["name"], "Cambium West Sector")
        self.assertEqual(ubiquiti_target["name"], "Ubiquiti North Sector")

    def test_monitoring_prefers_configured_target_name_over_discovered_name(self):
        self.scan_targets.write_text(
            json.dumps(
                {
                    "cambium": [],
                    "ubiquiti": [{"ip": "10.0.0.21", "name": "North Ridge Manual Name"}],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        with self.app.app_context():
            upsert_devices(
                "ubiquiti",
                [
                    {
                        "mac": "00:11:22:33:44:99",
                        "username": "sub-z",
                        "sector_name": "Auto Detected Name",
                        "sector_ip": "10.0.0.21",
                        "timestamp": "2026-04-25T10:00:00Z",
                    }
                ],
            )
            upsert_sector_targets(
                "ubiquiti",
                [
                    {
                        "sector_name": "Saved Dashboard Name",
                        "sector_ip": "10.0.0.21",
                        "source_detail": "Ubiquiti dashboard",
                        "timestamp": "2026-04-25T10:00:00Z",
                    }
                ],
            )
            targets = build_monitor_targets(self.app)

        ubiquiti_target = next(item for item in targets if item["ip"] == "10.0.0.21")
        self.assertEqual(ubiquiti_target["name"], "North Ridge Manual Name")
        self.assertEqual(ubiquiti_target["detail"], "1 subscriber records seen on latest inventory")

    def test_monitoring_prefers_saved_zero_subscriber_ubiquiti_sector_name(self):
        with self.app.app_context():
            upsert_sector_targets(
                "ubiquiti",
                [
                    {
                        "sector_name": "North Ridge Rocket",
                        "sector_ip": "10.0.0.6",
                        "source_detail": "Ubiquiti dashboard",
                        "timestamp": "2026-04-25T10:00:00Z",
                    }
                ],
            )
            targets = build_monitor_targets(self.app)

        ubiquiti_target = next(item for item in targets if item["ip"] == "10.0.0.6")
        self.assertEqual(ubiquiti_target["name"], "North Ridge Rocket")
        self.assertEqual(ubiquiti_target["detail"], "Name captured from Ubiquiti dashboard")

    def test_monitoring_prefers_saved_zero_subscriber_cambium_sector_name(self):
        self.scan_targets.write_text(
            json.dumps(
                {
                    "cambium": ["10.0.0.20"],
                    "ubiquiti": [],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        with self.app.app_context():
            upsert_sector_targets(
                "cambium",
                [
                    {
                        "sector_name": "West Tower AP",
                        "sector_ip": "10.0.0.20",
                        "source_detail": "Cambium dashboard",
                        "timestamp": "2026-04-25T10:00:00Z",
                    }
                ],
            )
            targets = build_monitor_targets(self.app)

        cambium_target = next(item for item in targets if item["ip"] == "10.0.0.20")
        self.assertEqual(cambium_target["name"], "West Tower AP")
        self.assertEqual(cambium_target["detail"], "Name captured from Cambium dashboard")


if __name__ == "__main__":
    unittest.main()
