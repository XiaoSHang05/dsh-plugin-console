# -*- coding: utf-8 -*-
"""
装 dsh-prompt-history 1.6.7（一次性脚本）

它提供：输入框历史 —— ↑↓ 翻，Ctrl+R 反向搜索，前缀匹配
作者 xiaoffy，标准 DSH 插件（有 dsh.bundle）

⚠️ 必须 DSH 完全退出才能跑（改 node_modules 会让活进程崩）
"""

import io
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, r"D:\大鲸鱼的工作间\DSH工作区\插件管家")
import backend

PKG = "dsh-prompt-history"
VER = "1.6.7"


def log(s=""):
    print(s, flush=True)


def main():
    log("=" * 60)
    log("  装 %s %s" % (PKG, VER))
    log("=" * 60)
    log()

    n = backend.dsh_process_count()
    if n > 0:
        log("!! DSH 正在运行（%d 个进程），先彻底退出再跑" % n)
        log("   托盘图标右键 → 退出")
        return 2

    log("DSH 已关闭 ✓")
    log()

    # 已经装过就跳过
    pj, _, deps, bundles = backend.read_profile()
    if PKG in deps:
        log("已经装过了，版本: %s" % deps[PKG])
        if PKG not in bundles:
            log("但没挂 bundles，补挂…")
            backend.mount_bundles([PKG], log)
        return 0

    # 备份
    log("备份中…")
    backup = backend.make_backup("install")
    log("  → %s" % backup)
    log()

    # 摘出 git 依赖
    parked, restore = backend.park_non_registry()
    if parked:
        log("临时摘出 %d 个本地/git 依赖（避免 pnpm 去连 GitHub）" % parked)
        log()

    # 装
    log("安装中…")
    log("-" * 60)
    code = backend.run_pnpm(["add", "%s@%s" % (PKG, VER), "-E"], log)
    log("-" * 60)
    log()

    restore()
    if parked:
        log("已放回 %d 个本地/git 依赖" % parked)
        log()

    # 挂 bundles
    log("挂 bundles…")
    added = backend.mount_bundles([PKG], log)
    log()

    # 验证
    log("=" * 60)
    log("  验证")
    log("=" * 60)
    pj2, _, deps2, bundles2 = backend.read_profile()
    ver = backend.local_version(PKG)
    log("  版本        : %s" % (ver or "读不到"))
    log("  dependencies: %s" % ("Y" if PKG in deps2 else "N"))
    log("  bundles     : %s" % ("Y" if PKG in bundles2 else "N"))
    log("  bundles 总数: %d" % len(bundles2))
    log()

    ok = (ver == VER and PKG in deps2 and PKG in bundles2)
    if ok:
        log("✓ 装好了。重新打开 DSH 就能用：")
        log("  · ↑ / ↓     翻历史")
        log("  · Ctrl+R    反向搜索")
        log("  · 输入前缀再按 ↑  按前缀过滤")
    else:
        log("✗ 有项没到位，看上面哪一行是 N")
        log("  回滚：把 %s 里的文件复制回 profile" % backup)
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
