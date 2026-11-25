import unittest

from holder_gate import HolderGate


class HolderGateTest(unittest.TestCase):
    def test_waits_for_both_presentations(self):
        gate = HolderGate(5)
        self.assertEqual(gate.begin(10), "present-wallpaper")
        self.assertIsNone(gate.event(11, "greeter-presented"))
        self.assertEqual(gate.event(12, "wallpaper-presented"),
                         "stop-desktop-and-start-greeter")
        self.assertIsNone(gate.event(13, "greeter-connected"))
        self.assertEqual(gate.event(14, "greeter-presented"), "release-holder")
        self.assertIsNone(gate.event(15, "tick"))

    def test_timeout_before_or_after_wallpaper(self):
        for wallpaper_ready in (False, True):
            with self.subTest(wallpaper_ready=wallpaper_ready):
                gate = HolderGate(5)
                gate.begin(10)
                if wallpaper_ready:
                    gate.event(11, "wallpaper-presented")
                self.assertEqual(gate.event(15, "tick"), "restore-stock")
                self.assertIsNone(gate.event(16, "greeter-presented"))

    def test_greeter_failure(self):
        gate = HolderGate(5)
        gate.begin(10)
        gate.event(11, "wallpaper-presented")
        self.assertEqual(gate.event(12, "failed"), "restore-stock")
