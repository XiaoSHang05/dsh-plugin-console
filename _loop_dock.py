# -*- coding: utf-8 -*-
"""
Phase 1 反馈回路：检查 dsh-dock 的本地修改会不会被判定成"可更新"

断言的是「用户的具体症状」：
  ① dsh-dock 有本地修改的文件
  ② 扫描结果里 dsh-dock 是不是 UPDATE（是 → 就会被覆盖）
  ③ 如果本地版本 == 云端版本，那就不该出现在可更新列表里
"""
import io
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, r"D:\大鲸鱼的工作间\DSH工作区\插件管家")

import backend  # noqa: E402
from pathlib import Path  # noqa: E402

PKG = "dsh-dock"


def main():
    print("=" * 60)
    print(f"反馈回路：{PKG} 会不会被误判成可更新")
    print("=" * 60)

    # ① 本地有没有被改过
    pkgdir = backend.PROFILE / "node_modules" / PKG
    print(f"\n[1] 包目录: {pkgdir}")
    print(f"    存在: {pkgdir.exists()}")

    local_ver = backend.local_version(PKG)
    print(f"    本地版本: {local_ver}")

    # ② 云端最新版
    latest = backend.fetch_latest(PKG)
    print(f"\n[2] 云端最新: {latest.get('version')}")

    # ③ 扫描判定
    sc = backend.scan_all()
    row = next((r for r in sc["rows"] if r["name"] == PKG), None)
    if row:
        print(f"\n[3] 扫描判定: {row['verdict']}")
        print(f"    当前版本: {row.get('cur')}")
        print(f"    最新版本: {row.get('latest')}")
        print(f"    是否可更新: {row['verdict'] == 'UPDATE'}")
    else:
        print(f"\n[3] 扫描结果里没有 {PKG}")

    print()
    print("=" * 60)
    if row and row["verdict"] == "UPDATE":
        print("FAIL: 会被覆盖！症状复现")
        return 1
    print("PASS: 不会被覆盖")
    return 0


if __name__ == "__main__":
    sys.exit(main())
