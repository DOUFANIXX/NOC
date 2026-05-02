import unittest

from app.utils.validation import (
    FormValidationError,
    is_valid_ip,
    validate_description,
    validate_daily_schedule_payload,
    validate_port_name,
    validate_positive_int,
    validate_switch_inventory_payload,
    validate_user_payload,
)


class ValidationTests(unittest.TestCase):
    def test_ip_validation(self):
        self.assertTrue(is_valid_ip("10.0.0.1"))
        self.assertFalse(is_valid_ip("999.10.10.10"))

    def test_description_validation(self):
        self.assertEqual(validate_description("Customer A / Port 3"), "Customer A / Port 3")
        with self.assertRaises(ValueError):
            validate_description("x")

    def test_port_validation(self):
        self.assertEqual(validate_port_name("GE1/0/9"), "GE1/0/9")
        with self.assertRaises(ValueError):
            validate_port_name("Fa0/1")

    def test_positive_int_validation(self):
        self.assertEqual(validate_positive_int("12", "switch"), 12)
        with self.assertRaises(ValueError):
            validate_positive_int("0", "switch")

    def test_switch_inventory_validation(self):
        cleaned = validate_switch_inventory_payload(
            {
                "inventory_type": "ultra",
                "city": "Tripoli",
                "area": "Almarri",
                "site": "",
                "name": "SW-CORE-01",
                "ip": "10.0.0.10",
                "notes": "Distribution switch",
            }
        )
        self.assertEqual(cleaned["inventory_type"], "ultra")
        with self.assertRaises(FormValidationError):
            validate_switch_inventory_payload(
                {
                    "inventory_type": "ht",
                    "city": "",
                    "area": "",
                    "site": "",
                    "name": "X",
                    "ip": "999.10.10.10",
                    "notes": "",
                }
            )

    def test_user_validation(self):
        cleaned = validate_user_payload(
            {
                "username": "viewer_1",
                "role": "viewer",
                "ui_preference": "light",
                "password": "StrongPass123",
            }
        )
        self.assertEqual(cleaned["role"], "viewer")
        self.assertEqual(cleaned["ui_preference"], "light")
        with self.assertRaises(FormValidationError):
            validate_user_payload(
                {
                    "username": "x",
                    "role": "bad-role",
                    "password": "123",
                }
            )

    def test_daily_schedule_validation(self):
        cleaned = validate_daily_schedule_payload(
            {
                "vendor": "cambium",
                "enabled": "on",
                "daily_time": "01:30",
            }
        )
        self.assertEqual(cleaned["daily_time"], "01:30")
        with self.assertRaises(FormValidationError):
            validate_daily_schedule_payload(
                {
                    "vendor": "ubiquiti",
                    "enabled": "on",
                    "daily_time": "25:99",
                }
            )


if __name__ == "__main__":
    unittest.main()
