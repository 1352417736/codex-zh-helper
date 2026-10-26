"""Queue-based UI controller; worker threads never manipulate Tk widgets."""

from pathlib import Path
import os
import queue
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox

from . import service, storage
from .view import View


def phase_for(message):
    phases = [
        ("读取当前版本", "正在准备翻译内容……"),
        ("校验所有", "正在检查翻译结果……"),
        ("复制当前安装", "正在复制程序，首次生成可能需要一点时间……"),
        ("写入界面", "正在保存并校验汉化副本……"),
        ("同步副本", "正在完成启动适配……"),
        ("正在强制退出", "正在关闭原版，随后打开汉化版……"),
        ("启动实际界面", "正在打开汉化版……"),
    ]
    return next((text for prefix, text in phases if message.startswith(prefix)), None)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.events = queue.Queue()
        self.view = View(
            self,
            {
                "detect": self.detect,
                "browse": self.browse,
                "prepare": self.prepare,
                "launch": self.launch,
                "original": self.original,
                "logs": self.open_logs,
            },
        )
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.after(80, self.drain)
        self.after(150, self.detect)

    def emit(self, message):
        storage.logger().info(message)
        self.events.put(("log", message))

    def run_work(self, title, job, success):
        if self.view.is_busy:
            return
        self.view.busy(True)
        self.view.message(title)
        self.emit(title)

        def work():
            try:
                self.events.put(("success", (job(), success)))
            except Exception as error:
                storage.logger().exception("Operation failed")
                self.events.put(("error", str(error)))

        threading.Thread(target=work, daemon=True).start()

    def drain(self):
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == "log":
                    self.view.append(time.strftime("%H:%M:%S") + "  " + value)
                    phase = phase_for(value)
                    if phase:
                        self.view.message(phase)
                elif kind == "success":
                    result, message = value
                    self.view.busy(False)
                    if isinstance(result, service.Overview):
                        self.view.update(result)
                    self.view.message(message)
                elif kind == "error":
                    self.view.busy(False)
                    self.view.append("未完成：" + value)
                    self.view.message(value, error=True)
        except queue.Empty:
            pass
        self.after(80, self.drain)

    def detect(self):
        selected = self.view.path.get().strip()
        self.run_work(
            "正在检测安装和中文资源……",
            lambda: service.overview(selected),
            "检测完成。可以生成副本，或启动已准备的汉化版。",
        )

    def browse(self):
        selected = filedialog.askdirectory(title="选择原版 Codex 安装目录")
        if selected:
            self.view.path.set(str(Path(selected)))
            self.detect()

    def prepare(self):
        selected = self.view.path.get().strip()
        self.run_work(
            "正在准备汉化副本，请稍候……",
            lambda: service.prepare(selected, self.emit),
            "汉化副本已准备。保存工作后，点击“启动汉化版”。",
        )

    def launch(self):
        self.run_work(
            "正在校验副本并切换，请稍候……",
            lambda: service.launch_localized(self.emit),
            "已确认汉化版进程持续运行。",
        )

    def original(self):
        selected = self.view.path.get().strip()
        self.run_work(
            "正在切换到原版……", lambda: service.launch_original(selected, self.emit), "已请求启动原版。"
        )

    def open_logs(self):
        storage.DATA.mkdir(parents=True, exist_ok=True)
        os.startfile(storage.DATA)

    def close(self):
        if self.view.is_busy:
            messagebox.showinfo("正在处理", "请等待当前操作完成后再关闭助手。")
        else:
            self.destroy()


def main():
    if os.name == "nt":
        try:
            import ctypes

            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except (AttributeError, OSError):
            pass
    App().mainloop()
