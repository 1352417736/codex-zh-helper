import argparse
import sys

from . import __version__


def main():
    parser = argparse.ArgumentParser(description="Codex 中文助手")
    parser.add_argument("--version", action="version", version=__version__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--launch-copy", action="store_true", help="退出原版并启动汉化副本")
    group.add_argument("--launch-original", action="store_true", help="退出副本并返回原版")
    args = parser.parse_args()
    if not (args.launch_copy or args.launch_original):
        from .app import main as run

        run()
        return
    from . import service, storage

    def log(message):
        storage.logger().info(message)
        if sys.stdout is not None:
            print(message, flush=True)

    try:
        if args.launch_copy:
            service.launch_localized(log)
        else:
            service.launch_original(log=log)
    except Exception as error:
        storage.logger().exception("Launch failed")
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("启动未完成", str(error) + "\n日志目录：" + str(storage.DATA))
        root.destroy()
        raise SystemExit(1)


if __name__ == "__main__":
    main()
