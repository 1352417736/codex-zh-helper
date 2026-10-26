import tkinter as tk
import unittest

from codex_zh_helper.app import phase_for
from codex_zh_helper.service import Overview
from codex_zh_helper.view import View


class ViewTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(str(error))
        self.root.withdraw()
        callbacks = {
            key: lambda: None for key in ["detect", "browse", "prepare", "launch", "original", "logs"]
        }
        self.view = View(self.root, callbacks)

    def tearDown(self):
        if hasattr(self, "root"):
            self.root.destroy()

    def test_actions_follow_ready_and_busy_state(self):
        self.assertEqual(str(self.view.launch["state"]), "disabled")
        self.view.update(Overview("source", "1.0", 100, True, True))
        self.assertEqual(str(self.view.launch["state"]), "normal")
        self.view.busy(True)
        self.assertTrue(all(str(button["state"]) == "disabled" for button in self.view.buttons))
        self.view.busy(False)
        self.assertEqual(str(self.view.launch["state"]), "normal")

    def test_details_are_collapsed_and_log_is_readonly(self):
        self.assertFalse(self.view.details.winfo_manager())
        self.view.append("test")
        self.assertEqual(str(self.view.text["state"]), "disabled")
        self.view.toggle_details()
        self.assertTrue(self.view.details.winfo_manager())

    def test_phase_messages_hide_implementation_details(self):
        self.assertEqual(phase_for("读取当前版本的中文词典并生成补丁计划……"), "正在准备翻译内容……")
        self.assertIsNone(phase_for("unrelated diagnostic"))
