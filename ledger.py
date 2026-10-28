# -*- coding: utf-8 -*-
"""
插件管家 · 台账同步模块

把 node_modules 里的真实版本号写回 DSH插件台账.md：
  ① §一 表格的「版本」格 → 换成真实版本 + 🕒 日期
  ② §七 更新记录 → 追加一行（旧的 → 新的）

设计原则：任何异常都不抛，只返回结果；台账不存在就安静跳过。
"""

import json
import re
import shutil
from datetime import datetime
from pathlib import Path

# 这些由 backend 注入，避免循环 import
_PROFILE = None
_BACKUP_ROOT = None
_LOCAL_VERSION = None
_READ_PROFILE = None

LEDGER_KEEP_BACKUPS = 3


def bind(profile, backup_root, local_version_fn, read_profile_fn):
    """由 backend 调用，注入依赖"""
    global _PROFILE, _BACKUP_ROOT, _LOCAL_VERSION, _READ_PROFILE
    _PROFILE = profile
    _BACKUP_ROOT = backup_root
    _LOCAL_VERSION = local_version_fn
    _READ_PROFILE = read_profile_fn


def load_config():
    try:
        f = Path(__file__).parent / "config.json"
        if f.exists():
            return json.loads(f.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def ledger_path():
    """台账路径来自 config.json。
    没配 → 返回 None（开源版默认：不启用台账同步）"""
    p = load_config().get("ledgerPath")
    if not p:
        return None
    import os
    p = os.path.expandvars(os.path.expanduser(str(p)))
    return Path(p)


def _clean_name(cell):
    """从台账第一列提取纯包名。
    实际格式样例：
      ' **dsh-univer-office** '
      ' 🆕 **@tt-a1i/archify-dsh**（2026-10-18 新增） '
      ' 🆕 dsh-ops（自动补登） '
    """
    s = str(cell).strip()
    # ① 先剥掉 🆕 标记
    s = re.sub(r"^🆕\s*", "", s)
    # ② 优先抓 **...** 里的内容（最可靠）
    m = re.search(r"\*\*(.+?)\*\*", s)
    if m:
        return m.group(1).strip()
    # ③ 没有加粗：去掉各种括号补充，再取第一段
    s = re.sub(r"[（(][^）)]*[）)]", "", s)
    s = s.replace("*", "").strip()
    return s


def sync(on_log=None):
    """主入口。返回 dict。"""
    log = on_log or (lambda s: None)

    if _LOCAL_VERSION is None or _READ_PROFILE is None:
        return {"ok": False, "error": "台账模块未初始化"}

    L = ledger_path()
    if L is None:
        # 开源版默认：不配台账 → 静默跳过，不报错
        return {"ok": True, "skipped": True, "reason": "未配置台账",
                "changed": False, "patched": [], "records": 0, "missing": []}
    if not L.exists():
        return {"ok": False, "error": "台账不存在：%s" % L, "skipped": True}

    try:
        raw = L.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return {"ok": False, "error": str(e)}

    # 归一化孤立 CR（否则行数和显示都会错）
    raw = re.sub(r"\r(?!\n)", "", raw)
    lines = raw.split("\n")

    pj, _, deps, bundles = _READ_PROFILE()

    # ---------- ① 找 §一 表格
    head = None
    for i, l in enumerate(lines):
        if re.match(r"^\|\s*插件\s*\|\s*干什么的\s*\|", l):
            head = i
            break
    if head is None:
        return {"ok": False, "error": "台账里没找到 §一 表格"}

    today = datetime.now().strftime("%Y-%m-%d")
    patched = []
    seen = set()

    i = head + 2
    while i < len(lines) and lines[i].startswith("|"):
        cells = lines[i].strip("|").split("|")
        if len(cells) >= 3:
            nm = _clean_name(cells[0])
            seen.add(nm)
            if nm in deps:
                ver = _LOCAL_VERSION(nm)
                if ver:
                    m = re.search(r"\*\*([0-9][^<*\s]*)\*\*", cells[2])
                    old_ver = m.group(1) if m else ""
                    if old_ver != ver:
                        cells[2] = "    **%s**<br>🕒 %s 更新 " % (ver, today)
                        lines[i] = "|" + "|".join(cells) + "|"
                        patched.append((nm, old_ver, ver))
        i += 1

    missing = [nm for nm in deps if nm not in seen]

    # ---------- ② 追加 §七 更新记录
    #   ⚠️ 只记「真的变过」的（old 非空）。
    #   台账原来版本格是空的（新补登的插件）→ 只补 §一，不往 §七 塞假记录。
    records = 0
    real_changes = [(nm, old, new) for nm, old, new in patched if old]
    if real_changes:
        sec7 = None
        for j, l in enumerate(lines):
            if re.match(r"^\|\s*日期\s*\|\s*插件\s*\|\s*从\s*→\s*到\s*\|", l):
                sec7 = j
                break
        if sec7 is not None:
            k = sec7 + 2
            while k < len(lines) and lines[k].startswith("|"):
                k += 1
            rows = []
            for nm, old, new in real_changes:
                rows.append("| %s | %s | %s → **%s** | %s |" %
                            (today, nm, old, new, new))
            if rows:
                lines[k:k] = rows
                records = len(rows)

    out = "\n".join(lines)
    if out == raw:
        return {
            "ok": True, "changed": False, "patched": [], "records": 0,
            "missing": missing, "backup": None,
        }

    # ---------- ③ 备份 + 轮转
    backup = None
    try:
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        bdir = Path(_BACKUP_ROOT) / "ledger"
        bdir.mkdir(parents=True, exist_ok=True)
        backup = str(bdir / ("%s.bak-%s-台账同步前%s" % (L.stem, ts, L.suffix)))
        shutil.copy2(L, backup)
        olds = sorted([p for p in bdir.iterdir() if p.is_file()])
        for o in olds[:max(0, len(olds) - LEDGER_KEEP_BACKUPS)]:
            try:
                o.unlink()
            except Exception:
                pass
    except Exception as e:
        log("台账备份失败（不影响写入）：%s" % e)

    L.write_text(out, encoding="utf-8")

    return {
        "ok": True,
        "changed": True,
        "patched": [{"name": n, "from": o, "to": v} for n, o, v in patched],
        "records": records,
        "missing": missing,
        "backup": backup,
    }
