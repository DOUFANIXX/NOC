import shutil
import unittest
from datetime import datetime, timezone
from pathlib import Path

from app import create_app
from app.services.jobs_service import create_job
from app.services.scan_schedule_service import get_schedule, save_schedule, should_enqueue_scheduled_scan


TEST_ROOT = Path(".tmp-tests-scan-schedule")


class ScanScheduleServiceTests(unittest.TestCase):
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
        self.app = create_app(
            {
                "TESTING": True,
                "INSTANCE_PATH": self.temp_dir,
                "DATABASE_PATH": self.temp_dir / "test.sqlite3",
                "LOG_DIR": self.temp_dir / "logs",
                "SECRET_KEY": "test-secret",
                "BOOTSTRAP_ADMIN_PASSWORD": "StrongPass123",
            }
        )

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_daily_schedule_due_once_per_day(self):
        with self.app.app_context():
            save_schedule("cambium", True, "10:00")

            self.assertFalse(
                should_enqueue_scheduled_scan(
                    "cambium",
                    now=datetime(2026, 4, 23, 9, 59, tzinfo=timezone.utc),
                )
            )
            self.assertTrue(
                should_enqueue_scheduled_scan(
                    "cambium",
                    now=datetime(2026, 4, 23, 10, 5, tzinfo=timezone.utc),
                )
            )

            create_job("scan", "cambium", "scheduler", None)

            self.assertFalse(
                should_enqueue_scheduled_scan(
                    "cambium",
                    now=datetime(2026, 4, 23, 10, 10, tzinfo=timezone.utc),
                )
            )

    def test_get_schedule_defaults_to_disabled(self):
        with self.app.app_context():
            schedule = get_schedule("ubiquiti")
            self.assertFalse(schedule["enabled"])
            self.assertEqual(schedule["daily_time"], "")


if __name__ == "__main__":
    unittest.main()
