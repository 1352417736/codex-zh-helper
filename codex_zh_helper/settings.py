"""Supported locale preference and installed-app discovery."""

import json
import os
from pathlib import Path
import re
import subprocess
import time
import tomllib
from .storage import CONFIG, BACKUPS as STATE

SECTION = re.compile(r"^\s*\[desktop\]\s*(?:#.*)?$", re.M)
HEADER = re.compile(r"^\s*\[", re.M)
LOCALE = re.compile(r'^(\s*localeOverride\s*=\s*)([\'"])[^\r\n]*?\2(\s*(?:#.*)?)$', re.M)


def edit_locale(text: str, value: str | None) -> str:
    """Change only desktop.localeOverride, keeping other settings and comments."""
    tomllib.loads(text)
    newline = "\r\n" if "\r\n" in text else "\n"
    match = SECTION.search(text)
    if match is None:
        result = (
            text
            if value is None
            else text.rstrip()
            + newline * 2
            + "[desktop]"
            + newline
            + f"localeOverride = {json.dumps(value)}"
            + newline
        )
    else:
        end = HEADER.search(text, match.end())
        stop = end.start() if end else len(text)
        block = text[match.end() : stop]
        old = LOCALE.search(block)
        if old:
            replacement = "" if value is None else old[1] + json.dumps(value) + old[3]
            block = block[: old.start()] + replacement + block[old.end() :]
        elif value is not None:
            block = newline + f"localeOverride = {json.dumps(value)}" + block
            if not block.endswith(("\r", "\n")):
                block += newline
        result = text[: match.end()] + block + text[stop:]
    parsed = tomllib.loads(result)
    if parsed.get("desktop", {}).get("localeOverride") != value:
        raise ValueError("配置校验失败，未写入文件")
    return result


def write_config(value: str | None) -> Path | None:
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    original = CONFIG.read_bytes() if CONFIG.exists() else b""
    text = original.decode("utf-8-sig")
    result = edit_locale(text, value).encode("utf-8")
    if result == original:
        return None
    STATE.mkdir(parents=True, exist_ok=True)
    backup = STATE / (time.strftime("%Y%m%d-%H%M%S") + f"-{time.time_ns() % 1000000}.toml")
    backup.write_bytes(original)
    temp = CONFIG.with_name("config.zh-helper-" + str(os.getpid()) + ".tmp")
    temp.write_bytes(result)
    try:
        if (CONFIG.read_bytes() if CONFIG.exists() else b"") != original:
            raise RuntimeError("配置刚被其他程序修改，请重试")
        os.replace(temp, CONFIG)
    finally:
        temp.unlink(missing_ok=True)
    return backup


def detect_app() -> Path | None:
    command = "Get-AppxPackage -Name OpenAI.Codex | Select-Object -ExpandProperty InstallLocation"
    try:
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
            capture_output=True,
            timeout=20,
            creationflags=0x08000000,
        )
        for line in result.stdout.decode("utf-8", errors="replace").splitlines():
            candidate = Path(line.strip()) / "app"
            if (candidate / "resources" / "app.asar").is_file():
                return candidate
    except (OSError, subprocess.TimeoutExpired):
        pass
    for root in [
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Codex",
        Path("C:/Program Files/Codex"),
    ]:
        if (root / "resources" / "app.asar").is_file():
            return root
    return None
