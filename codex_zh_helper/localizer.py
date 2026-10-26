"""Version-aware, reversible translation of display message defaults in a copy."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import time

STRING = r'(?:`(?:\\.|[^`\\])*`|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\')'
PAIR = re.compile(r'(?P<key>"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\')\s*:\s*(?P<value>' + STRING + ")")
MESSAGE = re.compile(r"\b(?:id|messageId):(?P<id>" + STRING + r"),defaultMessage:(?P<value>" + STRING + ")")
ARGS = re.compile(r"\{\s*([A-Za-z_]\w*)\s*[,}]")
TAGS = re.compile(r"</?([A-Za-z_]\w*)\b[^>]*>")


def decode_literal(token):
    if token[0] == '"':
        return json.loads(token)
    if token[0] == "`" and "${" in token:
        raise ValueError("Interpolated template is not a display literal")
    body = token[1:-1]
    # The shipped locale catalog primarily uses plain template strings.
    return re.sub(
        r'\\(u[0-9a-fA-F]{4}|[\\`\'"nrtbf/])',
        lambda m: (
            chr(int(m[1][1:], 16))
            if m[1].startswith("u")
            else {"n": "\n", "r": "\r", "t": "\t", "b": "\b", "f": "\f"}.get(m[1], m[1])
        ),
        body,
    )


def compatible(english, chinese):
    return set(ARGS.findall(english)) == set(ARGS.findall(chinese)) and set(TAGS.findall(english)) == set(
        TAGS.findall(chinese)
    )


class Archive:
    def __init__(self, path):
        self.path = Path(path)
        with self.path.open("rb") as stream:
            raw = stream.read(16)
            if len(raw) != 16:
                raise ValueError("ASAR 文件不完整")
            magic, size, _, length = struct.unpack("<4I", raw)
            if magic != 4 or not 0 < length < 32 * 1024 * 1024:
                raise ValueError("未知 ASAR 格式")
            self.header = json.loads(stream.read(length))
            self.base = 8 + size
        self.files = {}
        self.walk(self.header)

    def walk(self, node, prefix=""):
        for key, value in node.get("files", {}).items():
            name = prefix + key
            if "files" in value:
                self.walk(value, name + "/")
            else:
                self.files[name] = value

    def read(self, name):
        entry = self.files[name]
        if entry.get("unpacked") or "offset" not in entry:
            raise ValueError("文件不在 ASAR 数据区：" + name)
        with self.path.open("rb") as stream:
            stream.seek(self.base + int(entry["offset"]))
            data = stream.read(entry["size"])
        if len(data) != entry["size"]:
            raise ValueError("文件长度校验失败：" + name)
        return data

    def write(self, target, replacements):
        entries = sorted(
            (
                (name, entry)
                for name, entry in self.files.items()
                if "offset" in entry and not entry.get("unpacked")
            ),
            key=lambda pair: int(pair[1]["offset"]),
        )
        old_offsets = {name: int(entry["offset"]) for name, entry in entries}
        offset = 0
        for name, entry in entries:
            if name in replacements:
                data = replacements[name]
                block_size = entry.get("integrity", {}).get("blockSize", 4 * 1024 * 1024)
                entry["size"] = len(data)
                entry["integrity"] = {
                    "algorithm": "SHA256",
                    "hash": hashlib.sha256(data).hexdigest(),
                    "blockSize": block_size,
                    "blocks": [
                        hashlib.sha256(data[i : i + block_size]).hexdigest()
                        for i in range(0, len(data), block_size)
                    ]
                    or [hashlib.sha256(b"").hexdigest()],
                }
            entry["offset"] = str(offset)
            offset += entry["size"]
        payload = json.dumps(self.header, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        size = (4 + len(payload) + 3) & ~3
        encoded = (
            struct.pack("<4I", 4, size + 4, size, len(payload)) + payload + b"\0" * (size - 4 - len(payload))
        )
        with self.path.open("rb") as source, Path(target).open("wb") as dest:
            dest.write(encoded)
            for name, entry in entries:
                if name in replacements:
                    dest.write(replacements[name])
                    continue
                source.seek(self.base + old_offsets[name])
                remaining = entry["size"]
                while remaining:
                    chunk = source.read(min(remaining, 4 * 1024 * 1024))
                    if not chunk:
                        raise ValueError("源 ASAR 数据不完整")
                    dest.write(chunk)
                    remaining -= len(chunk)


def translate(source, catalog):
    changed = []
    skipped = []

    def replace(match):
        try:
            key = decode_literal(match["id"])
            english = decode_literal(match["value"])
        except (ValueError, json.JSONDecodeError):
            return match[0]
        chinese = catalog.get(key)
        if not chinese or chinese == english:
            return match[0]
        if not compatible(english, chinese):
            skipped.append(key)
            return match[0]
        changed.append(key)
        start = match.start("value") - match.start()
        return match[0][:start] + json.dumps(chinese, ensure_ascii=False)

    return MESSAGE.sub(replace, source), changed, skipped


def plan(archive):
    names = [name for name in archive.files if re.fullmatch(r"webview/assets/zh-CN-[^/]+\.js", name)]
    if len(names) != 1:
        raise ValueError("未找到唯一的内置中文词典，此版本需要单独适配")
    catalog = {}
    for match in PAIR.finditer(archive.read(names[0]).decode("utf-8")):
        try:
            key, value = decode_literal(match["key"]), decode_literal(match["value"])
            if re.search("[\u3400-\u9fff]", value):
                catalog[key] = value
        except (ValueError, json.JSONDecodeError):
            pass
    if len(catalog) < 100:
        raise ValueError("当前中文词典格式不受支持")
    replacements, changes, skipped = {}, {}, []
    # Only message descriptors in UI bundles; no runtime switches, permissions,
    # request parameters, backend modules, locale catalogs, or user content.
    for name in archive.files:
        if not name.startswith("webview/assets/") or not name.endswith(".js"):
            continue
        if re.search(r"/[a-z]{2}(?:-[A-Z][a-zA-Z]+)?-[a-f0-9]+\.js$", name):
            continue
        entry = archive.files[name]
        if entry.get("unpacked") or "offset" not in entry:
            continue
        data = archive.read(name)
        if b"defaultMessage:" not in data:
            continue
        source = data.decode("utf-8")
        updated, ids, missed = translate(source, catalog)
        if ids:
            replacements[name] = updated.encode("utf-8")
            changes[name] = ids
        skipped.extend(missed)
    return replacements, changes, sorted(set(skipped)), len(catalog)


def file_hash(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def header_hash(path):
    with Path(path).open("rb") as stream:
        header = stream.read(16)
        if len(header) != 16:
            raise ValueError("归档头部不完整")
        length = struct.unpack("<4I", header)[3]
        return hashlib.sha256(stream.read(length)).hexdigest()


INTEGRITY = re.compile(rb'"file":"resources[^\r\n]{0,20}app\.asar","alg":"SHA256","value":"([0-9a-f]{64})')


def launcher_integrity(source_app, archive):
    expected = header_hash(archive)
    result = []
    for name in ["Codex.exe", "ChatGPT.exe"]:
        path = Path(source_app) / name
        if not path.exists():
            continue
        data = path.read_bytes()
        matches = list(INTEGRITY.finditer(data))
        if len(matches) > 1:
            raise ValueError("启动器包含多个资源绑定记录，需要单独适配")
        for match in matches:
            if match[1].decode("ascii") != expected:
                raise ValueError("启动器与当前资源校验不一致，停止修改")
            result.append((name, match.start(1), expected))
    return result


def sync_copy_integrity(source_app, copy_app, records, archive):
    updated = header_hash(archive).encode("ascii")
    results = []
    for name, offset, expected in records:
        original = (Path(source_app) / name).read_bytes()
        path = Path(copy_app) / name
        data = path.read_bytes()
        if data != original or data[offset : offset + 64] != expected.encode("ascii"):
            raise ValueError("副本启动器发生变化，停止修改")
        changed = data[:offset] + updated + data[offset + 64 :]
        path.write_bytes(changed)
        reread = path.read_bytes()
        if (
            reread[:offset] != original[:offset]
            or reread[offset + 64 :] != original[offset + 64 :]
            or reread[offset : offset + 64] != updated
        ):
            raise ValueError("副本校验值同步失败")
        results.append(
            {
                "file": name,
                "source_sha256": hashlib.sha256(original).hexdigest(),
                "patched_sha256": hashlib.sha256(reread).hexdigest(),
                "offset": offset,
            }
        )
    return results


def validate_javascript(replacements):
    node = shutil.which("node")
    if not node:
        raise ValueError("需要安装 Node.js 以校验修改后的 JavaScript 语法")
    checker = "const vm=require('node:vm');let s='';process.stdin.setEncoding('utf8');process.stdin.on('data',c=>s+=c);process.stdin.on('end',()=>{for(const [name,code] of JSON.parse(s)){try{new vm.SourceTextModule(code,{identifier:name})}catch(e){console.error(name+': '+e.message);process.exit(1)}}console.log('syntax OK')});"
    result = subprocess.run(
        [node, "--experimental-vm-modules", "-e", checker],
        input=json.dumps(
            [(name, data.decode("utf-8")) for name, data in replacements.items()], ensure_ascii=False
        ),
        text=True,
        encoding="utf-8",
        capture_output=True,
        timeout=90,
        creationflags=0x08000000 if os.name == "nt" else 0,
    )
    if result.returncode:
        raise ValueError("修改后 JavaScript 语法校验失败：" + result.stderr[:1000])


def verify(source, target, replacements):
    original, patched = Archive(source), Archive(target)
    if set(original.files) != set(patched.files):
        raise ValueError("补丁改变了归档文件列表")
    for name, expected in replacements.items():
        data = patched.read(name)
        if data != expected:
            raise ValueError("补丁内容校验失败：" + name)
        integrity = patched.files[name]["integrity"]
        if hashlib.sha256(data).hexdigest() != integrity["hash"]:
            raise ValueError("补丁哈希校验失败：" + name)
    # Stream-compare every unchanged packed file, including runtime and locales.
    with Path(source).open("rb") as first, Path(target).open("rb") as second:
        for name, entry in original.files.items():
            if name in replacements or "offset" not in entry or entry.get("unpacked"):
                continue
            first.seek(original.base + int(entry["offset"]))
            second.seek(patched.base + int(patched.files[name]["offset"]))
            remaining = entry["size"]
            while remaining:
                count = min(remaining, 4 * 1024 * 1024)
                if first.read(count) != second.read(count):
                    raise ValueError("未修改文件发生变化：" + name)
                remaining -= count


def install(source_app, output_root, log=None):
    if log is None:
        log = lambda message: None
    source_app, output_root = Path(source_app).resolve(), Path(output_root).resolve()
    source_archive = source_app / "resources" / "app.asar"
    if output_root == source_app or source_app in output_root.parents:
        raise ValueError("副本目录必须在源程序目录之外")
    if "windowsapps" in str(output_root).lower():
        raise ValueError("不向 WindowsApps 写入")
    records = launcher_integrity(source_app, source_archive)
    digest = file_hash(source_archive)
    version = source_app.parent.name if source_app.name.lower() == "app" else source_app.name
    key = hashlib.sha256((str(source_app) + digest).encode()).hexdigest()[:12]
    root = output_root / key
    manifest = root / "manifest.json"
    if manifest.exists():
        previous = json.loads(manifest.read_text(encoding="utf-8"))
        launcher_ok = all(
            (root / "app" / item["file"]).is_file()
            and file_hash(root / "app" / item["file"]) == item["patched_sha256"]
            for item in previous.get("launchers", [])
        )
        if (
            previous.get("source_sha256") == digest
            and file_hash(root / "app/resources/app.asar") == previous.get("patched_sha256")
            and launcher_ok
        ):
            from .processes import resolve_entry

            entry_name = resolve_entry(root / "app").name
            (root / "launch.cmd").write_bytes(
                ('@echo off\r\ncd /d "%~dp0app"\r\nstart "" "%~dp0app\\' + entry_name + '"\r\n').encode(
                    "ascii"
                )
            )
            log("此版本已安装且哈希校验通过，复用现有副本。")
            return root, previous
    log("读取当前版本的中文词典并生成补丁计划……")
    archive = Archive(source_archive)
    replacements, changes, skipped, catalog_size = plan(archive)
    if not changes:
        raise ValueError("没有匹配到可翻译的界面消息，此版本需要单独适配")
    log("校验所有待修改界面脚本的 JavaScript 语法……")
    validate_javascript(replacements)
    if root.exists():
        root = output_root / (key + "-" + str(time.time_ns()))
    app = root / "app"
    log("复制当前安装版本；原程序保留作为恢复版本……")
    shutil.copytree(source_app, app)
    log("写入界面文本并验证归档……")
    patched_archive = app / "resources/app.asar"
    temp = app / "resources/app.zh.tmp"
    archive.write(temp, replacements)
    verify(source_archive, temp, replacements)
    if file_hash(source_archive) != digest:
        raise ValueError("安装期间源程序发生更新，未激活该副本，请重新执行")
    os.replace(temp, patched_archive)
    log("同步副本中的资源校验值，并验证除此以外的启动器字节完全一致……")
    launchers = sync_copy_integrity(source_app, app, records, patched_archive)
    report = {
        "schema": 1,
        "source_app": str(source_app),
        "version": version,
        "source_sha256": digest,
        "patched_sha256": file_hash(patched_archive),
        "launchers": launchers,
        "catalog_entries": catalog_size,
        "translated_messages": sum(map(len, changes.values())),
        "changed_bundles": len(changes),
        "changes": changes,
        "skipped_incompatible": skipped,
        "method": "Translate display message defaults using bundled Simplified Chinese catalog; no runtime gate edits",
        "ui_verified": False,
    }
    (root / "manifest.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    from .processes import resolve_entry

    entry_name = resolve_entry(app).name
    launcher = '@echo off\r\ncd /d "%~dp0app"\r\nstart "" "%~dp0app\\' + entry_name + '"\r\n'
    (root / "launch.cmd").write_bytes(launcher.encode("ascii"))
    log(f"副本已准备：{report['translated_messages']} 条消息，{report['changed_bundles']} 个界面文件。")
    return root, report
