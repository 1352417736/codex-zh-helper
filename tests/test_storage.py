import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from codex_zh_helper import storage


class StorageTests(unittest.TestCase):
    def test_discovers_legacy_copy_without_bundled_active_file(self):
        with tempfile.TemporaryDirectory() as directory:
            copies = Path(directory) / "copies"
            root = copies / "test"
            (root / "app/resources").mkdir(parents=True)
            (root / "app/resources/app.asar").touch()
            (root / "manifest.json").write_text(json.dumps({"source_app": "original"}))
            with (
                patch.object(storage, "COPIES", copies),
                patch.object(storage, "ACTIVE", Path(directory) / "missing.json"),
            ):
                self.assertEqual(storage.load_active()[0], root.resolve())

    def test_does_not_trust_active_record_outside_copy_root(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            active = root / "active.json"
            active.write_text(json.dumps({"root": str(root / "outside")}))
            with patch.object(storage, "COPIES", root / "copies"), patch.object(storage, "ACTIVE", active):
                self.assertIsNone(storage.load_active())

    def test_save_active_is_local_and_atomic(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with (
                patch.object(storage, "DATA", root),
                patch.object(storage, "ACTIVE", root / "active.json"),
                patch.object(storage, "COPIES", root / "copies"),
            ):
                storage.save_active(root / "copies/test")
                self.assertEqual(
                    json.loads((root / "active.json").read_text())["root"],
                    str((root / "copies/test").resolve()),
                )
                self.assertFalse((root / "active.tmp").exists())
