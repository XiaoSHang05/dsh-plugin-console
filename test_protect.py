# -*- coding: utf-8 -*-
"""
插件管家 · 保护机制测试（TDD）

Seam（公共接口）：
  · is_pinned(name)          -> bool      C 方案：不许主动升级
  · protect_snapshot(names)  -> dict      A 方案：升级前备份本地改动
  · protect_restore(ts)      -> dict      A 方案：升级后还原
  · list_protected()         -> dict      读 protect.json

跑法：python test_protect.py
"""

import io
import json
import shutil
import sys
import tempfile
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

PASSED = []
FAILED = []


def test(name):
    def deco(fn):
        try:
            fn()
            PASSED.append(name)
            print(f"  PASS  {name}")
        except AssertionError as e:
            FAILED.append((name, str(e)))
            print(f"  FAIL  {name}")
            print(f"        {e}")
        except Exception as e:
            FAILED.append((name, f"{type(e).__name__}: {e}"))
            print(f"  ERR   {name}")
            print(f"        {type(e).__name__}: {e}")
        return fn
    return deco


# ---------------------------------------------------------------- 测试
def main():
    import backend

    print("=" * 60)
    print("保护机制测试")
    print("=" * 60)

    # ---------------- C 方案：pinned
    print("\n[C] pinned 名单")

    @test("is_pinned 对 dsh-dock 返回 True")
    def _():
        assert backend.is_pinned("dsh-dock") is True, "dsh-dock 应该被钉住"

    @test("is_pinned 对普通包返回 False")
    def _():
        assert backend.is_pinned("dsh-context") is False, "dsh-context 不该被钉住"

    @test("list_pinned 返回列表且含 dsh-dock")
    def _():
        lst = backend.list_pinned()
        assert isinstance(lst, list), f"应返回 list，实际 {type(lst)}"
        assert "dsh-dock" in lst, f"列表里应有 dsh-dock，实际 {lst}"

    # ---------------- A 方案：protect
    print("\n[A] 本地修改保护")

    @test("list_protected 能读到 dsh-dock 的受保护文件")
    def _():
        d = backend.list_protected()
        assert isinstance(d, dict), f"应返回 dict，实际 {type(d)}"
        assert "dsh-dock" in d, f"应含 dsh-dock，实际 {list(d)}"
        files = d["dsh-dock"].get("files") or []
        assert "features/notify/view.jsx" in files, f"应含 view.jsx，实际 {files}"

    @test("protect_snapshot 能备份出文件，且内容字节一致")
    def _():
        r = backend.protect_snapshot(["dsh-dock"])
        assert r.get("ok") is True, f"应成功，实际 {r}"
        assert r.get("count", 0) > 0, f"应备份至少 1 个文件，实际 {r}"
        # 检查备份文件真的存在且字节一致
        ts = r["ts"]
        saved = backend.protect_backup_dir(ts)
        assert saved.exists(), f"备份目录应存在: {saved}"
        one = next(saved.rglob("view.jsx"), None)
        assert one is not None, f"备份里应有 view.jsx，实际 {list(saved.rglob('*'))[:5]}"
        src = backend.PROFILE / "node_modules" / "dsh-dock" / "features" / "notify" / "view.jsx"
        assert one.read_bytes() == src.read_bytes(), "备份内容应与原文件字节一致"

    @test("protect_restore 能把被篡改的文件还原")
    def _():
        # 先备份
        r = backend.protect_snapshot(["dsh-dock"])
        ts = r["ts"]
        target = backend.PROFILE / "node_modules" / "dsh-dock" / "features" / "notify" / "view.jsx"
        good = target.read_bytes()

        # 模拟 pnpm 覆盖：写入垃圾
        target.write_bytes(b"// OVERWRITTEN BY PNPM\n")

        # 还原
        rr = backend.protect_restore(ts)
        assert rr.get("ok") is True, f"应成功，实际 {rr}"
        assert rr.get("restored", 0) > 0, f"应还原至少 1 个，实际 {rr}"
        assert target.read_bytes() == good, "文件应被还原成原内容"

    # ---------------- 集成：升级流程要用上这两个
    print("\n[集成] 升级流程")

    @test("do_update 会跳过 pinned 包")
    def _():
        # 直接调，pinned 包不该进 targets
        logs = []
        r = backend.do_update(["dsh-dock"], logs.append)
        assert r.get("ok") is False, f"应该拒绝（没有可更新目标），实际 {r}"
        msg = (r.get("error") or "")
        assert "没有可更新" in msg or "钉住" in msg or "pinned" in msg.lower(), \
            f"错误信息应说明被跳过，实际: {msg}"

    # ---------------- 汇总
    print("\n" + "=" * 60)
    print(f"通过 {len(PASSED)} / {len(PASSED) + len(FAILED)}")
    if FAILED:
        print("\n失败项：")
        for n, why in FAILED:
            print(f"  · {n}")
            print(f"    {why}")
        return 1
    print("全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
