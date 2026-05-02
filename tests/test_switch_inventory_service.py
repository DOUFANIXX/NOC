import json
import shutil
import unittest
from pathlib import Path

from app import create_app
from app.services.switch_inventory_service import (
    add_switch_record,
    delete_switch_record,
    get_switch_record,
    list_inventory,
    seed_inventory_from_files,
)


TEST_ROOT = Path(".tmp-tests-switch-inventory")


class SwitchInventoryServiceTests(unittest.TestCase):
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
        self.ultra_seed = self.temp_dir / "switch_inventory.seed.json"
        self.ht_seed = self.temp_dir / "ht_switch_inventory.seed.json"
        self._write_json(
            self.ultra_seed,
            {
                "Tripoli": {
                    "Almarri": {
                        "Main": {"ip": "10.52.2.1"},
                    }
                }
            },
        )
        self._write_json(
            self.ht_seed,
            {
                "HT MALL": {
                    "SW Main": {"ip": "10.40.1.1"},
                }
            },
        )
        self.app = create_app(
            {
                "TESTING": True,
                "INSTANCE_PATH": self.temp_dir,
                "DATABASE_PATH": self.temp_dir / "test.sqlite3",
                "LOG_DIR": self.temp_dir / "logs",
                "SECRET_KEY": "test-secret",
                "BOOTSTRAP_ADMIN_PASSWORD": "StrongPass123",
                "SWITCH_INVENTORY_SEED_FILE": self.ultra_seed,
                "HT_SWITCH_INVENTORY_SEED_FILE": self.ht_seed,
            }
        )

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _write_json(self, path: Path, payload: dict) -> None:
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    def _read_json(self, path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))

    def test_seed_sync_replaces_stale_db_rows(self):
        with self.app.app_context():
            self.assertEqual(len(list_inventory("ultra")), 1)
            self._write_json(
                self.ultra_seed,
                {
                    "Tripoli": {
                        "Bengarsa": {
                            "Only Switch": {"ip": "10.52.3.1"},
                        }
                    }
                },
            )

            seed_inventory_from_files(self.app)

            ultra_records = list_inventory("ultra")
            self.assertEqual(len(ultra_records), 1)
            self.assertEqual(ultra_records[0]["city"], "Tripoli")
            self.assertEqual(ultra_records[0]["area"], "Bengarsa")
            self.assertEqual(ultra_records[0]["name"], "Only Switch")
            self.assertEqual(ultra_records[0]["ip"], "10.52.3.1")

    def test_add_switch_record_updates_seed_and_db(self):
        with self.app.app_context():
            switch_id = add_switch_record(
                {
                    "inventory_type": "ultra",
                    "city": "Tripoli",
                    "area": "Bengarsa",
                    "site": "",
                    "name": "Ben Dgeam",
                    "ip": "10.52.3.2",
                    "notes": "Distribution switch",
                }
            )

            record = get_switch_record(switch_id)
            seed_data = self._read_json(self.ultra_seed)

            self.assertIsNotNone(record)
            self.assertEqual(record["name"], "Ben Dgeam")
            self.assertEqual(record["ip"], "10.52.3.2")
            self.assertEqual(
                seed_data["Tripoli"]["Bengarsa"]["Ben Dgeam"],
                {"ip": "10.52.3.2", "notes": "Distribution switch"},
            )

    def test_delete_switch_record_updates_seed_and_db(self):
        with self.app.app_context():
            record = list_inventory("ultra")[0]
            deleted = delete_switch_record(record["id"])

            self.assertIsNotNone(deleted)
            self.assertEqual(list_inventory("ultra"), [])
            self.assertEqual(self._read_json(self.ultra_seed), {})


if __name__ == "__main__":
    unittest.main()
