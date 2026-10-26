"""Local state stays outside the source tree and release archive."""

import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path

CODEX_HOME = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex")))
CONFIG = CODEX_HOME / "config.toml"
DATA = CODEX_HOME / "zh-cn-helper"
COPIES = CODEX_HOME / "zh-cn-ui"
BACKUPS = DATA / "backups"
ACTIVE = DATA / "active.json"
LOG = DATA / "helper.log"
RUNTIME_LOG = DATA / "runtime.log"


def logger():
    result = logging.getLogger("codex_zh_helper")
    if not result.handlers:
        DATA.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(LOG, maxBytes=1024 * 1024, backupCount=2, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        result.addHandler(handler)
        result.setLevel(logging.INFO)
    return result


def save_active(root):
    root = Path(root).resolve()
    if COPIES.resolve() not in root.parents:
        raise ValueError("副本位置不在工具管理目录中")
    DATA.mkdir(parents=True, exist_ok=True)
    temp = ACTIVE.with_suffix(".tmp")
    temp.write_text(json.dumps({"root": str(root)}, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temp, ACTIVE)


def load_active():
    candidates = []
    if ACTIVE.is_file():
        try:
            candidates.append(Path(json.loads(ACTIVE.read_text(encoding="utf-8"))["root"]))
        except (ValueError, KeyError, OSError):
            pass
    # Discover copies created by older releases without publishing local paths.
    if COPIES.is_dir():
        candidates.extend(
            sorted(
                (p.parent for p in COPIES.glob("*/manifest.json")),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
        )
    for root in candidates:
        root = root.resolve()
        if COPIES.resolve() not in root.parents:
            continue
        try:
            manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
            if manifest.get("source_app") and (root / "app/resources/app.asar").is_file():
                return root, manifest
        except (ValueError, OSError):
            pass
    return None
