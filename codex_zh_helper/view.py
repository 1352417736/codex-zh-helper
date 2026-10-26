"""Tk widgets and visual styles; no filesystem or process operations."""

import tkinter as tk
from pathlib import Path
from tkinter import scrolledtext, ttk

BG = "#F3F6FA"
WHITE = "#FFFFFF"
INK = "#172A3A"
MUTED = "#64748B"
ACCENT = "#087F72"
BORDER = "#DEE6EE"


class Button(tk.Button):
    def __init__(self, parent, text, command, primary=False):
        self.normal = ACCENT if primary else WHITE
        self.hover = "#06685E" if primary else "#EAF3F1"
        super().__init__(
            parent,
            text=text,
            command=command,
            font=("Microsoft YaHei UI", 10, "bold"),
            bg=self.normal,
            fg=WHITE if primary else INK,
            activebackground=self.hover,
            activeforeground=WHITE if primary else INK,
            relief="flat",
            borderwidth=0,
            padx=18,
            pady=11,
            cursor="hand2",
            disabledforeground="#9BAAB7",
            takefocus=True,
        )
        self.bind("<Enter>", lambda _: self.configure(bg=self.hover) if self["state"] == "normal" else None)
        self.bind("<Leave>", lambda _: self.configure(bg=self.normal))


def label(parent, text="", size=10, color=INK, bold=False, **kwargs):
    return tk.Label(
        parent,
        text=text,
        bg=parent["bg"],
        fg=color,
        font=("Microsoft YaHei UI", size, "bold" if bold else "normal"),
        **kwargs,
    )


def card(parent):
    return tk.Frame(parent, bg=WHITE, highlightbackground=BORDER, highlightthickness=1, padx=22, pady=18)


class View:
    def __init__(self, root, callbacks):
        self.root = root
        root.title("Codex 中文助手")
        assets = Path(__file__).parent / "assets"
        self.icon = tk.PhotoImage(master=root, file=str(assets / "app.png"))
        root.iconphoto(True, self.icon)
        if root.tk.call("tk", "windowingsystem") == "win32":
            root.iconbitmap(str(assets / "app.ico"))
        root.geometry("1080x800")
        root.minsize(1000, 740)
        root.configure(bg=BG)
        style = ttk.Style(root)
        style.theme_use("clam")
        style.configure(
            "Zh.Horizontal.TProgressbar",
            background=ACCENT,
            troughcolor="#DFE9E6",
            borderwidth=0,
            lightcolor=ACCENT,
            darkcolor=ACCENT,
        )
        self.buttons = []
        shell = tk.Frame(root, bg=BG)
        shell.pack(fill="both", expand=True)
        sidebar = tk.Frame(shell, bg=INK, width=214, padx=22, pady=30)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)
        label(sidebar, "中", 30, WHITE, True).pack(anchor="w")
        label(sidebar, "Codex 中文助手", 15, WHITE, True).pack(anchor="w", pady=(8, 4))
        label(sidebar, "让熟悉的界面\n说你的语言。", 11, "#AFC3D0", justify="left").pack(
            anchor="w", pady=(0, 32)
        )
        for number, title, description in [
            ("01", "检测安装", "找到当前 Codex 版本"),
            ("02", "生成副本", "保留原版，独立汉化"),
            ("03", "一键切换", "退出原版，打开汉化版"),
        ]:
            label(sidebar, number, 10, "#71D0BC", True).pack(anchor="w", pady=(14, 3))
            label(sidebar, title, 11, WHITE, True).pack(anchor="w")
            label(sidebar, description, 9, "#AFC3D0").pack(anchor="w", pady=(5, 10))
        label(sidebar, "WINDOWS  ·  v1.0", 9, "#AFC3D0").pack(side="bottom", anchor="w")

        main = tk.Frame(shell, bg=BG, padx=28, pady=24)
        main.pack(side="left", fill="both", expand=True)
        heading = tk.Frame(main, bg=BG)
        heading.pack(fill="x")
        label(heading, "界面汉化", 23, INK, True).pack(side="left")
        self.badge = label(heading, "●  等待检测", 10, ACCENT, True)
        self.badge.pack(side="right", pady=8)
        label(main, "更新后，重新生成副本即可继续使用。", 10, MUTED).pack(anchor="w", pady=(5, 20))

        source = card(main)
        source.pack(fill="x")
        source_top = tk.Frame(source, bg=WHITE)
        source_top.pack(fill="x")
        label(source_top, "Codex 安装位置", 11, INK, True).pack(side="left")
        self.add_button(source_top, "检测安装", callbacks["detect"]).pack(side="right")
        row = tk.Frame(source, bg=WHITE)
        row.pack(fill="x", pady=(10, 0))
        self.path = tk.StringVar()
        self.entry = tk.Entry(
            row,
            textvariable=self.path,
            font=("Segoe UI", 10),
            bg="#F6F8FB",
            fg=INK,
            relief="flat",
            highlightthickness=1,
            highlightbackground=BORDER,
            highlightcolor=ACCENT,
            insertbackground=INK,
        )
        self.entry.pack(side="left", fill="x", expand=True, ipady=11, padx=(0, 10))
        self.add_button(row, "选择目录", callbacks["browse"]).pack(side="right")

        metrics = tk.Frame(main, bg=BG)
        metrics.pack(fill="x", pady=14)
        metrics.grid_columnconfigure(0, weight=1, uniform="metric")
        metrics.grid_columnconfigure(1, weight=1, uniform="metric")
        left = card(metrics)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 7))
        right = card(metrics)
        right.grid(row=0, column=1, sticky="nsew", padx=(7, 0))
        label(left, "当前版本", 9, MUTED).pack(anchor="w")
        self.version = label(left, "—", 17, INK, True)
        self.version.pack(anchor="w", pady=(7, 0))
        label(right, "汉化副本", 9, MUTED).pack(anchor="w")
        self.copy = label(right, "尚未生成", 17, INK, True)
        self.copy.pack(anchor="w", pady=(7, 0))

        action = card(main)
        action.pack(fill="x")
        self.status = label(
            action, "先检测安装，再生成汉化副本。", 11, INK, True, anchor="w", justify="left", wraplength=690
        )
        self.status.pack(fill="x")
        self.progress = ttk.Progressbar(action, style="Zh.Horizontal.TProgressbar", mode="indeterminate")
        self.progress.pack(fill="x", pady=(14, 16), ipady=1)
        controls = tk.Frame(action, bg=WHITE)
        controls.pack(fill="x")
        self.prepare = self.add_button(controls, "生成汉化副本", callbacks["prepare"], True)
        self.prepare.pack(side="left")
        self.launch = self.add_button(controls, "启动汉化版", callbacks["launch"])
        self.launch.pack(side="left", padx=10)
        self.add_button(controls, "返回原版", callbacks["original"]).pack(side="right")
        label(action, "切换版本会结束当前对应的 Codex 进程，请先保存工作。", 9, MUTED).pack(
            anchor="w", pady=(14, 0)
        )

        details_bar = tk.Frame(main, bg=BG)
        details_bar.pack(fill="x", pady=(12, 5))
        self.toggle = self.add_button(details_bar, "展开运行详情", self.toggle_details)
        self.toggle.pack(side="left")
        self.add_button(details_bar, "打开日志目录", callbacks["logs"]).pack(side="right")
        self.details = tk.Frame(main, bg=BG)
        self.text = scrolledtext.ScrolledText(
            self.details,
            height=5,
            font=("Microsoft YaHei UI", 9),
            bg=WHITE,
            fg=MUTED,
            relief="flat",
            borderwidth=0,
            padx=12,
            pady=10,
            wrap="word",
            state="disabled",
        )
        self.text.pack(fill="both", expand=True)
        label(main, "原版文件保留。此工具为社区项目，与 OpenAI 无隶属关系。", 9, MUTED).pack(
            side="bottom", anchor="w", pady=(8, 0)
        )
        self.is_busy = False
        self.ready = False
        self.available = False
        self.apply_actions()

    def add_button(self, parent, text, command, primary=False):
        button = Button(parent, text, command, primary)
        self.buttons.append(button)
        return button

    def toggle_details(self):
        if self.details.winfo_manager():
            self.details.pack_forget()
            self.toggle.configure(text="展开运行详情")
        else:
            self.details.pack(fill="both", expand=True)
            self.toggle.configure(text="收起运行详情")

    def append(self, message):
        self.text.configure(state="normal")
        self.text.insert("end", message + "\n")
        if int(self.text.index("end-1c").split(".")[0]) > 350:
            self.text.delete("1.0", "50.0")
        self.text.see("end")
        self.text.configure(state="disabled")

    def update(self, overview):
        self.path.set(overview.source)
        self.version.configure(text=overview.version)
        self.ready = overview.copy_ready
        self.available = overview.chinese_available
        self.copy.configure(text=f"{overview.translation_count:,} 处消息" if self.ready else "尚未生成")
        self.badge.configure(text="●  副本已记录" if self.ready else "●  已找到安装", fg=ACCENT)
        self.prepare.configure(text="更新汉化副本" if self.ready else "生成汉化副本")
        self.apply_actions()

    def apply_actions(self):
        for button in self.buttons:
            button.configure(state="disabled" if self.is_busy else "normal")
        if not self.is_busy:
            self.launch.configure(state="normal" if self.ready else "disabled")
            self.prepare.configure(state="normal" if self.available else "disabled")
        self.entry.configure(state="disabled" if self.is_busy else "normal")

    def busy(self, value):
        self.is_busy = value
        self.apply_actions()
        if value:
            self.progress.start(12)
            self.badge.configure(text="●  正在处理", fg=ACCENT)
        else:
            self.progress.stop()
            self.progress.configure(value=0)

    def message(self, message, error=False):
        self.status.configure(text=message, fg="#B5473C" if error else INK)
        if not self.is_busy:
            self.badge.configure(
                text="●  需要处理" if error else "●  就绪", fg="#B5473C" if error else ACCENT
            )
