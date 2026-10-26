"""Stop only GUI processes whose executable paths match the original app."""

import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import subprocess
import time


def gui_paths(app):
    return {
        os.path.normcase(os.path.abspath(Path(app) / name))
        for name in ("Codex.exe", "ChatGPT.exe", "chrome.exe")
    }


def resolve_entry(app):
    app = Path(app)
    codex, runtime = app / "Codex.exe", app / "ChatGPT.exe"
    if codex.is_file():
        is_trampoline = (
            codex.stat().st_size < 128 * 1024
            and "Windows.ApplicationModel.Package".encode("utf-16le") in codex.read_bytes()
        )
        if not is_trampoline:
            return codex
        if not runtime.is_file():
            raise ValueError("检测到 Store 激活跳板，但副本缺少实际界面程序 ChatGPT.exe")
        return runtime
    if runtime.is_file():
        return runtime
    raise ValueError("副本缺少可用的界面启动程序")


def matching_processes(app):
    if os.name != "nt":
        raise RuntimeError("此功能仅支持 Windows")
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)

    class ProcessEntry(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD),
            ("cntUsage", wintypes.DWORD),
            ("th32ProcessID", wintypes.DWORD),
            ("th32DefaultHeapID", ctypes.c_size_t),
            ("th32ModuleID", wintypes.DWORD),
            ("cntThreads", wintypes.DWORD),
            ("th32ParentProcessID", wintypes.DWORD),
            ("pcPriClassBase", wintypes.LONG),
            ("dwFlags", wintypes.DWORD),
            ("szExeFile", wintypes.WCHAR * 260),
        ]

    kernel.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    kernel.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(ProcessEntry)]
    kernel.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(ProcessEntry)]
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.QueryFullProcessImageNameW.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.LPWSTR,
        ctypes.POINTER(wintypes.DWORD),
    ]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    snapshot = kernel.CreateToolhelp32Snapshot(2, 0)
    if snapshot == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    wanted = gui_paths(app)
    found = []
    try:
        entry = ProcessEntry()
        entry.dwSize = ctypes.sizeof(entry)
        more = kernel.Process32FirstW(snapshot, ctypes.byref(entry))
        while more:
            if entry.th32ProcessID != os.getpid() and entry.szExeFile.lower() in (
                "codex.exe",
                "chatgpt.exe",
                "chrome.exe",
            ):
                handle = kernel.OpenProcess(0x1000, False, entry.th32ProcessID)
                if handle:
                    try:
                        buffer = ctypes.create_unicode_buffer(32768)
                        length = wintypes.DWORD(len(buffer))
                        if (
                            kernel.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(length))
                            and os.path.normcase(os.path.abspath(buffer.value)) in wanted
                        ):
                            found.append((entry.th32ProcessID, buffer.value))
                    finally:
                        kernel.CloseHandle(handle)
            more = kernel.Process32NextW(snapshot, ctypes.byref(entry))
    finally:
        kernel.CloseHandle(snapshot)
    return found


def terminate_matched(pid, expected_path):
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.QueryFullProcessImageNameW.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.LPWSTR,
        ctypes.POINTER(wintypes.DWORD),
    ]
    kernel.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
    kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel.WaitForSingleObject.restype = wintypes.DWORD
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.OpenProcess(0x101001, False, pid)
    if not handle:
        error = ctypes.get_last_error()
        if error == 87:  # The process has already exited.
            return
        raise ctypes.WinError(error)
    try:
        if kernel.WaitForSingleObject(handle, 0) == 0:
            return
        buffer = ctypes.create_unicode_buffer(32768)
        length = wintypes.DWORD(len(buffer))
        if not kernel.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(length)):
            error = ctypes.get_last_error()
            if kernel.WaitForSingleObject(handle, 0) == 0:
                return
            raise ctypes.WinError(error)
        if os.path.normcase(os.path.abspath(buffer.value)) != os.path.normcase(
            os.path.abspath(expected_path)
        ):
            raise RuntimeError("进程路径发生变化，未结束该进程")
        if not kernel.TerminateProcess(handle, 0):
            error = ctypes.get_last_error()
            if kernel.WaitForSingleObject(handle, 0) == 0:
                return
            raise ctypes.WinError(error)
    finally:
        kernel.CloseHandle(handle)


def stop_original(
    app,
    log=lambda message: None,
    *,
    find=matching_processes,
    terminate=terminate_matched,
    timeout=15,
    clock=time.monotonic,
    pause=time.sleep,
):
    deadline = clock() + timeout
    stopped = set()
    denied = set()
    while True:
        processes = find(app)
        if not processes:
            log(f"原版已退出，结束 {len(stopped)} 个界面进程。")
            return
        if clock() >= deadline:
            blocked = sorted(pid for pid, _ in processes if pid in denied)
            if blocked:
                raise RuntimeError(
                    "原版仍有进程拒绝结束（PID："
                    + ",".join(map(str, blocked))
                    + "）。请手动退出原版；若原版以管理员权限运行，可用相同权限打开助手后重试。未启动副本。"
                )
            raise RuntimeError("原版进程未能完全退出，已取消启动副本")
        for pid, path in processes:
            if pid not in stopped:
                if pid not in denied:
                    log(f"正在强制退出原版界面进程：{pid}")
                try:
                    terminate(pid, path)
                except OSError as error:
                    if getattr(error, "winerror", None) not in (5, 87):
                        raise
                    if pid not in denied:
                        log(f"进程 {pid} 可能正在退出，等待重新确认状态……")
                    denied.add(pid)
                    continue
                denied.discard(pid)
                stopped.add(pid)
        pause(0.15)


def switch_to_copy(
    source_app, copy_app, log=lambda message: None, *, stop=stop_original, start=subprocess.Popen
):
    copy_app = Path(copy_app)
    exe = resolve_entry(copy_app)
    stop(source_app, log)
    log("启动实际界面程序：" + str(exe))
    return start([str(exe)], cwd=copy_app)


def wait_for_copy(
    copy_app,
    process,
    log=lambda message: None,
    *,
    find=matching_processes,
    timeout=10,
    clock=time.monotonic,
    pause=time.sleep,
):
    deadline = clock() + timeout
    first_seen = None
    last_exit = None
    while clock() < deadline:
        found = find(copy_app)
        now = clock()
        if found:
            if first_seen is None:
                first_seen = now
            elif now - first_seen >= 2:
                log("已确认汉化副本进程持续运行。")
                return
        else:
            first_seen = None
            last_exit = process.poll()
            if last_exit is not None:
                raise RuntimeError(f"副本启动后退出，退出码：{last_exit}。请查看启动诊断日志。")
        pause(0.2)
    raise RuntimeError("启动超时，未确认副本持续运行。请查看启动诊断日志。")
