from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from codex_zh_helper import localizer, service


class ServiceTests(unittest.TestCase):
    def test_version_label(self):
        self.assertEqual(
            service.version_label("C:/WindowsApps/OpenAI.Codex_26.1021.3705.0_x64/app"), "26.1021.3705.0"
        )

    def test_prepare_saves_record_after_config_succeeds(self):
        with (
            patch.object(service, "find_source", return_value=Path("source")),
            patch.object(service, "install", return_value=(Path("copy"), {"translated_messages": 42})),
            patch.object(service, "write_config") as config,
            patch.object(service.storage, "save_active") as save,
        ):
            result = service.prepare()
            self.assertEqual(result.translation_count, 42)
            config.assert_called_once_with("zh-CN")
            save.assert_called_once_with(Path("copy"))

    def test_prepare_does_not_activate_when_config_write_fails(self):
        with (
            patch.object(service, "find_source", return_value=Path("source")),
            patch.object(service, "install", return_value=(Path("copy"), {"translated_messages": 42})),
            patch.object(service, "write_config", side_effect=OSError("write failed")),
            patch.object(service.storage, "save_active") as save,
        ):
            with self.assertRaises(OSError):
                service.prepare()
            save.assert_not_called()

    def test_corrupt_copy_is_rejected_before_switching(self):
        manifest = {"source_app": "source", "patched_sha256": "expected"}
        with (
            patch.object(service.storage, "load_active", return_value=(Path("copy"), manifest)),
            patch.object(service, "file_hash", return_value="wrong"),
            patch.object(service, "switch_to_copy") as switch,
        ):
            with self.assertRaises(ValueError):
                service.launch_localized()
            switch.assert_not_called()

    def test_same_version_reuses_copy_without_translation_scan(self):
        import hashlib, json

        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source"
            source.mkdir()
            output = Path(directory) / "copies"
            digest = "source-hash"
            key = hashlib.sha256((str(source.resolve()) + digest).encode()).hexdigest()[:12]
            root = output / key
            root.mkdir(parents=True)
            manifest = {"source_sha256": digest, "patched_sha256": "copy-hash", "launchers": []}
            (root / "manifest.json").write_text(json.dumps(manifest))
            with (
                patch.object(localizer, "launcher_integrity", return_value=[]),
                patch.object(localizer, "file_hash", side_effect=[digest, "copy-hash"]),
                patch("codex_zh_helper.processes.resolve_entry", return_value=Path("ChatGPT.exe")),
                patch.object(localizer, "plan") as scan,
            ):
                result, _ = localizer.install(source, output)
                self.assertEqual(result, root.resolve())
                scan.assert_not_called()
