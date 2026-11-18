import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import workaround_watcher as ww  # noqa: E402


def fake_vercmp(a: str, b: str) -> int:
    # Good enough for plain dotted versions; real runs use pacman's vercmp.
    left, right = (tuple(int(part) for part in v.split(".")) for v in (a, b))
    return (left > right) - (left < right)


class ConditionTest(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.object(ww, "vercmp", fake_vercmp)
        patcher.start()
        self.addCleanup(patcher.stop)

    def check(self, installed, when):
        with mock.patch.object(ww, "installed_version", return_value=installed):
            return ww.condition_met(when)

    def test_operators(self):
        self.assertTrue(self.check("6.12.1", {"pkg": "qt6-base", "ge": "6.12.1"}))
        self.assertFalse(self.check("6.12.0", {"pkg": "qt6-base", "ge": "6.12.1"}))
        self.assertTrue(self.check("6.12.0", {"pkg": "qt6-base", "lt": "6.12.1"}))
        self.assertFalse(self.check("6.12.1", {"pkg": "qt6-base", "gt": "6.12.1"}))

    def test_all_operators_must_hold(self):
        when = {"pkg": "qt6-base", "ge": "6.12.0", "lt": "6.13"}
        self.assertTrue(self.check("6.12.5", when))
        self.assertFalse(self.check("6.13.0", when))

    def test_missing_package_is_not_met(self):
        self.assertFalse(self.check(None, {"pkg": "nope", "ge": "1"}))

    def test_invalid_conditions(self):
        for when in ({"ge": "1"}, {"pkg": "x"}, {"pkg": "x", "gte": "1"}):
            with self.subTest(when=when), self.assertRaises(ValueError):
                self.check("1", when)
        with self.assertRaises(TypeError):
            self.check("1", "qt6-base")


class LoadTest(unittest.TestCase):
    def test_versions_stay_strings(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / "workarounds.yaml"
        path.write_text("- name: x\n  when: {pkg: p, ge: 6.10}\n")
        self.assertEqual(ww.load_entries(path)[0]["when"]["ge"], "6.10")


if __name__ == "__main__":
    unittest.main()
