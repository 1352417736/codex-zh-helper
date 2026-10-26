"""Application workflow: inspect, prepare, verify and switch versions."""

from dataclasses import dataclass
from pathlib import Path
import re
import subprocess

from . import storage
from .localizer import Archive, file_hash, install
from .processes import resolve_entry, stop_original, switch_to_copy, wait_for_copy
from .settings import detect_app, write_config


@dataclass
class Overview:
    source: str = ""
    version: str = "等待检测"
    translation_count: int = 0
    copy_ready: bool = False
    chinese_available: bool = False


def version_label(app):
    match = re.search(r"OpenAI\.Codex_([^_]+)", str(app))
    if match:
        return match[1]
    return Path(app).name


def find_source(selected=""):
    app = Path(selected).expanduser().resolve() if selected.strip() else detect_app()
    if app is None:
        active = storage.load_active()
        if active:
            candidate = Path(active[1]["source_app"])
            if (candidate / "resources/app.asar").is_file():
                app = candidate
    if app is None:
        raise ValueError("未找到 Codex，请点击“选择目录”指定安装目录。")
    if (app / "app/resources/app.asar").is_file():
        app = app / "app"
    if not (app / "resources/app.asar").is_file():
        raise ValueError("所选目录缺少 resources/app.asar，请选择实际程序目录。")
    if storage.COPIES.resolve() == app or storage.COPIES.resolve() in app.parents:
        raise ValueError("请选原版安装目录，而不是已经生成的汉化副本。")
    return app


def overview(selected=""):
    app = find_source(selected)
    archive = Archive(app / "resources/app.asar")
    available = any(re.fullmatch(r"webview/assets/zh-CN-[^/]+\.js", name) for name in archive.files)
    active = storage.load_active()
    ready = bool(active and Path(active[1]["source_app"]).resolve() == app.resolve())
    count = active[1].get("translated_messages", 0) if ready else 0
    return Overview(str(app), version_label(app), count, ready, available)


def prepare(selected="", log=lambda message: None):
    app = find_source(selected)
    root, manifest = install(app, storage.COPIES, log)
    write_config("zh-CN")
    storage.save_active(root)
    return Overview(str(app), version_label(app), manifest["translated_messages"], True, True)


def verified_active():
    active = storage.load_active()
    if active is None:
        raise ValueError("还没有可用的汉化副本，请先点击“生成汉化副本”。")
    root, manifest = active
    if file_hash(root / "app/resources/app.asar") != manifest["patched_sha256"]:
        raise ValueError("副本资源已改变，请重新生成汉化副本。")
    for item in manifest.get("launchers", []):
        filename = item["file"]
        if Path(filename).name != filename:
            raise ValueError("副本记录包含无效启动器路径。")
        if file_hash(root / "app" / filename) != item["patched_sha256"]:
            raise ValueError("副本启动器已改变，请重新生成汉化副本。")
    source = Path(manifest["source_app"])
    if (
        not (source / "resources/app.asar").is_file()
        or file_hash(source / "resources/app.asar") != manifest["source_sha256"]
    ):
        raise ValueError("Codex 已更新或移动，请先检测新版本并重新生成副本。")
    resolve_entry(root / "app")
    return root, source


def launch_localized(log=lambda message: None):
    log("正在校验汉化副本……")
    root, source = verified_active()
    storage.DATA.mkdir(parents=True, exist_ok=True)
    with storage.RUNTIME_LOG.open("a", encoding="utf-8") as stream:

        def start(args, **kwargs):
            return subprocess.Popen(args, stdout=stream, stderr=stream, **kwargs)

        process = switch_to_copy(source, root / "app", log, start=start)
        wait_for_copy(root / "app", process, log)


def launch_original(selected="", log=lambda message: None):
    source = find_source(selected)
    active = storage.load_active()
    if active:
        stop_original(active[0] / "app", lambda message: log(message.replace("原版", "汉化版")))
    exe = source / "Codex.exe"
    if not exe.is_file():
        exe = resolve_entry(source)
    subprocess.Popen([str(exe)], cwd=source)
    log("已请求启动保留的原版。")
