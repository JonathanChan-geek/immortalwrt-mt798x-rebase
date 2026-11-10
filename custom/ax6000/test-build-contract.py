#!/usr/bin/env python3
"""Exercise changed config gates without claiming defconfig/build acceptance."""
import contextlib
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("verify", HERE / "verify.py")
verify = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verify)


class ConfigContract(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.old_top = verify.TOP
        self.addCleanup(setattr, verify, "TOP", self.old_top)
        verify.TOP = Path(self.directory.name)
        target = verify.TOP / "custom/ax6000"
        target.mkdir(parents=True)
        self.seed = (HERE / "config.seed").read_text()
        (target / "config.seed").write_text(self.seed)
        self.actual = verify.TOP / ".config"
        self.actual.write_text((HERE / "wifi.config").read_text() + "\n" + self.seed)

    def test_single_core_adzero_candidate(self):
        with contextlib.redirect_stdout(io.StringIO()):
            verify.check_config()

    def test_honk_reintroduction_rejected(self):
        with self.actual.open("a") as output:
            output.write("\nCONFIG_PACKAGE_honk=y\n")
        with self.assertRaises(AssertionError):
            verify.check_config()

    def test_dropped_adzero_rejected(self):
        self.actual.write_text(self.actual.read_text().replace("CONFIG_PACKAGE_luci-app-adzero=y", ""))
        with self.assertRaisesRegex(AssertionError, "luci-app-adzero"):
            verify.check_config()


if __name__ == "__main__":
    unittest.main()
