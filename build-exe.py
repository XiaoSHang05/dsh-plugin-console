# -*- coding: utf-8 -*-
"""
打包成 exe（PyInstaller · onedir 模式）

为什么用 onedir 不用 onefile：
  onefile 运行时要把自己解压到临时目录（%TEMP%\_MEIxxxx），
  这台机器上创建一个临时目录失败（实测 [PYI-ERROR] Could not create temporary directory），
  exe 就直接退出。
  onedir 是「exe + 一个文件夹」，不碰临时目录，启动也快得多。

产物：dist\插件管家\插件管家.exe   （整个「插件管家」文件夹拷走即可）
"""

import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
DIST = HERE / "dist"
BUILD = HERE / "build"
NAME = "插件管家"


def build(console=False, name=None):
    name = name or NAME
    ico = HERE / "icon.ico"
    if not ico.exists():
        print(f"缺图标：{ico}")
        return 1

    for d in (DIST, BUILD):
        if d.exists():
            shutil.rmtree(d, ignore_errors=True)
    spec = HERE / f"{name}.spec"
    if spec.exists():
        spec.unlink()

    sep = ";"
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onedir",                      # ★ 不用 onefile
        "--console" if console else "--noconsole",
        f"--name={name}",
        f"--icon={ico}",
        f"--add-data={HERE / 'ui'}{sep}ui",
        f"--add-data={ico}{sep}.",
        f"--add-data={HERE / 'categories.json'}{sep}.",
        f"--add-data={HERE / 'descriptions.json'}{sep}.",
        f"--add-data={HERE / 'config.example.json'}{sep}.",
        "--hidden-import=webview",
        "--hidden-import=webview.platforms.winforms",
        "--collect-all=webview",
        str(HERE / "app.py"),
    ]

    print(f"打包 {name} ({'console' if console else 'noconsole'}) …")
    p = subprocess.run(cmd, cwd=str(HERE),
                       capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    tail = (p.stdout or "")[-600:]
    if p.returncode != 0:
        print("FAIL rc=%s" % p.returncode)
        print(tail)
        return p.returncode

    exe = DIST / name / f"{name}.exe"
    if not exe.exists():
        print("FAIL: 没生成 %s" % exe)
        return 1

    size = sum(f.stat().st_size for f in (DIST / name).rglob("*") if f.is_file()) / 1024 / 1024
    print("OK  %s" % exe)
    print("    整个文件夹 %.1f MB" % size)
    return 0


if __name__ == "__main__":
    console = "--console" in sys.argv
    returncode = build(console=console, name="pmc-debug" if console else None)
    sys.exit(returncode)
