from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

from codex_zh_helper import processes as s


class SwitchTests(unittest.TestCase):
    def test_access_denied_then_process_disappears_is_success(self):
        error = PermissionError("access denied")
        error.winerror = 5
        find = Mock(side_effect=[[(10, "original.exe")], []])
        s.stop_original("source", find=find, terminate=Mock(side_effect=error), pause=lambda _: None)
        self.assertEqual(find.call_count, 2)

    def test_persistent_access_denied_reports_actionable_error(self):
        error = PermissionError("access denied")
        error.winerror = 5
        with self.assertRaisesRegex(RuntimeError, "拒绝结束.*10"):
            s.stop_original(
                "source",
                find=lambda _: [(10, "original.exe")],
                terminate=Mock(side_effect=error),
                clock=Mock(side_effect=[0, 0, 16]),
                pause=lambda _: None,
            )

    def test_unrelated_os_error_is_not_ignored(self):
        with self.assertRaises(OSError):
            s.stop_original(
                "source",
                find=lambda _: [(10, "original.exe")],
                terminate=Mock(side_effect=OSError("unexpected")),
                pause=lambda _: None,
            )

    def test_store_trampoline_uses_actual_runtime(self):
        with tempfile.TemporaryDirectory() as directory:
            app = Path(directory)
            (app / "Codex.exe").write_bytes(b"MZ" + "Windows.ApplicationModel.Package".encode("utf-16le"))
            runtime = app / "ChatGPT.exe"
            runtime.touch()
            self.assertEqual(s.resolve_entry(app), runtime)
            start = Mock()
            s.switch_to_copy("source", app, stop=Mock(), start=start)
            self.assertEqual(start.call_args.args[0], [str(runtime)])

    def test_trampoline_without_runtime_fails_before_stop(self):
        with tempfile.TemporaryDirectory() as directory:
            app = Path(directory)
            (app / "Codex.exe").write_bytes("Windows.ApplicationModel.Package".encode("utf-16le"))
            stop = Mock()
            with self.assertRaises(ValueError):
                s.switch_to_copy("source", app, stop=stop, start=Mock())
            stop.assert_not_called()

    def test_exited_copy_is_failure(self):
        process = Mock()
        process.poll.return_value = 1
        with self.assertRaises(RuntimeError):
            s.wait_for_copy("copy", process, find=lambda _: [], pause=lambda _: None)

    def test_sustained_copy_is_success(self):
        s.wait_for_copy(
            "copy",
            Mock(),
            find=lambda _: [(10, "copy.exe")],
            clock=Mock(side_effect=[0, 0, 0, 1, 3]),
            pause=lambda _: None,
        )

    def test_waits_until_original_is_gone(self):
        find = Mock(side_effect=[[(10, "original.exe")], [(10, "original.exe")], []])
        kill = Mock()
        s.stop_original("source", find=find, terminate=kill, pause=lambda _: None)
        kill.assert_called_once_with(10, "original.exe")
        self.assertEqual(find.call_count, 3)

    def test_timeout(self):
        clock = Mock(side_effect=[0, 0, 16])
        with self.assertRaises(RuntimeError):
            s.stop_original(
                "source",
                find=lambda _: [(10, "original.exe")],
                terminate=Mock(),
                clock=clock,
                pause=lambda _: None,
            )

    def test_stops_before_launch(self):
        with tempfile.TemporaryDirectory() as directory:
            app = Path(directory)
            (app / "Codex.exe").touch()
            events = []
            s.switch_to_copy(
                "source",
                app,
                stop=lambda *_: events.append("stop"),
                start=lambda *a, **k: events.append("start"),
            )
            self.assertEqual(events, ["stop", "start"])

    def test_does_not_launch_when_stop_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            app = Path(directory)
            (app / "Codex.exe").touch()
            start = Mock()
            with self.assertRaises(RuntimeError):
                s.switch_to_copy("source", app, stop=Mock(side_effect=RuntimeError("failed")), start=start)
            start.assert_not_called()

    def test_missing_copy_does_not_stop_original(self):
        with tempfile.TemporaryDirectory() as directory:
            stop = Mock()
            with self.assertRaises(ValueError):
                s.switch_to_copy("source", directory, stop=stop, start=Mock())
            stop.assert_not_called()


if __name__ == "__main__":
    unittest.main()
