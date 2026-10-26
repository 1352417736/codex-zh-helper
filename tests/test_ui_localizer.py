import json
from pathlib import Path
import struct
import tempfile
import unittest

from codex_zh_helper import localizer as u


class TranslationTests(unittest.TestCase):
    def test_messages_only(self):
        source = "const m={id:`title`,defaultMessage:`Hello {name}`};const action={permission:`full`,method:`keep`};"
        updated, changed, _ = u.translate(source, {"title": "你好 {name}"})
        self.assertEqual(changed, ["title"])
        self.assertIn("permission:`full`,method:`keep`", updated)
        u.validate_javascript({"test.js": updated.encode()})

    def test_placeholder_mismatch_is_unchanged(self):
        source = "const m={id:`title`,defaultMessage:`Hello {name}`};"
        self.assertEqual(u.translate(source, {"title": "你好 {other}"})[0], source)
        self.assertEqual(u.translate(source, {"title": "你好 <link>{name}</link>"})[0], source)

    def test_interpolation_is_unchanged(self):
        source = "const m={id:`title`,defaultMessage:`Hello ${person}`};"
        self.assertEqual(u.translate(source, {"title": "你好"})[0], source)

    def test_idempotent(self):
        source = "const m={id:`title`,defaultMessage:`Hello`};"
        updated, _, _ = u.translate(source, {"title": "你好"})
        self.assertEqual(u.translate(updated, {"title": "你好"})[0], updated)

    def test_archive_roundtrip(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first, second = b"const a=1;", b"unchanged content"
            tree = {
                "files": {
                    "a.js": {"offset": "0", "size": len(first)},
                    "b.bin": {"offset": str(len(first)), "size": len(second)},
                }
            }
            payload = json.dumps(tree, separators=(",", ":")).encode()
            size = (4 + len(payload) + 3) & ~3
            source = root / "source.asar"
            source.write_bytes(
                struct.pack("<4I", 4, size + 4, size, len(payload))
                + payload
                + b"\0" * (size - 4 - len(payload))
                + first
                + second
            )
            target = root / "target.asar"
            changes = {"a.js": 'const a="中文";'.encode()}
            u.Archive(source).write(target, changes)
            u.verify(source, target, changes)
            self.assertEqual(u.Archive(target).read("b.bin"), second)


if __name__ == "__main__":
    unittest.main()
