import tempfile
from pathlib import Path
import tomllib
import unittest
from unittest.mock import patch

from codex_zh_helper import settings


class SettingsTests(unittest.TestCase):
    def test_preserves_other_settings_and_is_idempotent(self):
        cases = [
            "",
            'model = "keep"\n',
            '[desktop]\nappearanceTheme = "dark"\n[features]\na = true\n',
            '[desktop]\r\nlocaleOverride = "en-US" # keep\r\nappearanceTheme = "dark"\r\n[features]\r\na = true\r\n',
            "[desktop]\nlocaleOverride = 'en-US'\n",
        ]
        for source in cases:
            for locale in ["zh-CN", None, "en-US"]:
                with self.subTest(source=source, locale=locale):
                    result = settings.edit_locale(source, locale)
                    self.assertEqual(tomllib.loads(result).get("desktop", {}).get("localeOverride"), locale)
                    self.assertEqual(settings.edit_locale(result, locale), result)
                    before, after = tomllib.loads(source), tomllib.loads(result)
                    for parsed in [before, after]:
                        if "desktop" in parsed:
                            parsed["desktop"].pop("localeOverride", None)
                            if not parsed["desktop"]:
                                parsed.pop("desktop")
                    self.assertEqual(before, after)

    def test_backup_and_no_repeated_write(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "config.toml"
            config.write_text('[desktop]\nlocaleOverride = "en-US"\n', encoding="utf-8")
            with (
                patch.object(settings, "CONFIG", config),
                patch.object(settings, "STATE", Path(directory) / "backups"),
            ):
                backup = settings.write_config("zh-CN")
                self.assertEqual(tomllib.loads(backup.read_text())["desktop"]["localeOverride"], "en-US")
                self.assertIsNone(settings.write_config("zh-CN"))
