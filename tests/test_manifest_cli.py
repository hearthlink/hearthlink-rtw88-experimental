# SPDX-License-Identifier: GPL-2.0-only
"""CLI compatibility and integrity checks for reviewed manifest selection."""

import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


DRIVER_PATH = Path("drivers/net/wireless/realtek/rtw88")


@unittest.skipUnless(shutil.which("patch"), "GNU patch is required")
class ManifestCLI(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        self.repo = root / "repo"
        scripts = self.repo / "scripts"
        scripts.mkdir(parents=True)
        original = Path(__file__).resolve().parents[1] / "scripts/build.py"
        self.script = scripts / "build.py"
        shutil.copyfile(original, self.script)
        self.source = root / "source"
        files = {"usb.c": b"old source\n", "usb.h": b"USB header\n",
                 "main.h": b"shared header\n"}
        hashes = {}
        for name, content in files.items():
            relative = DRIVER_PATH / name
            path = self.source / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
            hashes[str(relative)] = hashlib.sha256(content).hexdigest()
        for name, release in (("SOURCE.json", "7.2.8+deb14-amd64"),
                              ("SOURCE-7.2.9.json", "7.2.9+deb14-amd64")):
            (self.repo / name).write_text(json.dumps({
                "source_file_sha256": hashes, "tested_kernel_release": release}))
        self.manifest = self.repo / "SOURCE-7.2.9.json"
        patches = self.repo / "patches"
        patches.mkdir()
        (patches / "series-queue-only").write_text("0001-fixture.patch\n")
        (patches / "0001-fixture.patch").write_text(
            f"--- a/{DRIVER_PATH}/usb.c\n+++ b/{DRIVER_PATH}/usb.c\n"
            "@@ -1 +1 @@\n-old source\n+new source\n")
        self.kdir = root / "headers"
        header = self.kdir / "include/generated/utsrelease.h"
        header.parent.mkdir(parents=True)
        self.header = header
        self.set_release("7.2.9+deb14-amd64")
        (self.kdir / "Module.symvers").write_text("nonempty fixture\n")
        self.output = root / "output"

    def set_release(self, release):
        self.header.write_text(f'#define UTS_RELEASE "{release}"\n')

    def run_helper(self, explicit_manifest):
        command = [sys.executable, str(self.script), "--source", str(self.source),
                   "--kdir", str(self.kdir), "--output", str(self.output),
                   "--prepare-only"]
        if explicit_manifest:
            command.extend(["--manifest", str(self.manifest)])
        return subprocess.run(command, capture_output=True, text=True, timeout=10)

    def test_explicit_target_applies_patch_and_records_selected_manifest(self):
        result = self.run_helper(True)
        self.assertEqual(result.returncode, 0, result.stderr)
        record = json.loads((self.output / "build-info.json").read_text())
        self.assertEqual(record["kernel_release"], "7.2.9+deb14-amd64")
        self.assertEqual(record["source_manifest_sha256"],
                         hashlib.sha256(self.manifest.read_bytes()).hexdigest())
        self.assertFalse(record["compiled"])
        patched = self.output / "source" / DRIVER_PATH / "usb.c"
        self.assertEqual(patched.read_bytes(), b"new source\n")

    def test_default_still_accepts_historical_headers(self):
        self.set_release("7.2.8+deb14-amd64")
        result = self.run_helper(False)
        self.assertEqual(result.returncode, 0, result.stderr)
        record = json.loads((self.output / "build-info.json").read_text())
        self.assertEqual(record["kernel_release"], "7.2.8+deb14-amd64")

    def test_default_rejects_new_headers_before_creating_output(self):
        result = self.run_helper(False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("kernel headers must target 7.2.8+deb14-amd64", result.stderr)
        self.assertFalse(self.output.exists())

    def test_explicit_manifest_rejects_modified_shared_header(self):
        (self.source / DRIVER_PATH / "main.h").write_text("changed layout\n")
        result = self.run_helper(True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("baseline mismatch", result.stderr)
        self.assertIn("main.h", result.stderr)
        self.assertFalse(self.output.exists())


if __name__ == "__main__":
    unittest.main()
