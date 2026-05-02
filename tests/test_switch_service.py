import unittest

from app.services.switch_service import _normalized_port_speed


class SwitchServiceTests(unittest.TestCase):
    def test_down_port_speed_is_na_even_if_switch_reports_numeric_speed(self):
        output = """
        GigabitEthernet0/0/1 current state : DOWN
        Line protocol current state : DOWN
        Speed : 1000
        """

        self.assertEqual(_normalized_port_speed(output, "DOWN"), "N/A")

    def test_up_port_keeps_numeric_speed(self):
        output = """
        GigabitEthernet0/0/1 current state : UP
        Speed : 1000
        """

        self.assertEqual(_normalized_port_speed(output, "UP"), "1000")

    def test_down_like_status_also_maps_speed_to_na(self):
        output = """
        GigabitEthernet0/0/1 current state : DOWN
        Speed : 1000
        """

        self.assertEqual(_normalized_port_speed(output, "Administratively DOWN"), "N/A")


if __name__ == "__main__":
    unittest.main()
