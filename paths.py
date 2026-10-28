# -*- coding: utf-8 -*-
"""
插件管家 · 配置与路径探测

目标：代码里不再有硬编码路径。
  · config.json 写了 → 用它
  · 没写（null） → 自动探测
  · 探测不到 → 给出清晰的报错，而不是崩

这样自用和开源是同一份代码，只是 config.json 内容不同。
"""

import json
import os
import re
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
CONFIG_FILE = APP_DIR / "config.json"

# 常见 DSH 安装位置（自动探测用）
DEFAULT_DSH_ROOTS = [
    r"E:\DSH-官方",
    r"D:\DSH官方",
    r"C:\Program Files\DSH",
    r"C:\Program Files\DeepSeek Harness",
    r"D:\Program Files\DSH",
]


_cfg_cache = {"mtime": 0, "data": None}


def load(force=False):
    """读 config.json（带缓存，文件变了自动重载）"""
    try:
        mtime = CONFIG_FILE.stat().st_mtime
    except Exception:
        return {}
    if not force and _cfg_cache["data"] is not None and _cfg_cache["mtime"] == mtime:
        return _cfg_cache["data"]
    try:
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        _cfg_cache["data"] = data
        _cfg_cache["mtime"] = mtime
        return data
    except Exception:
        return _cfg_cache["data"] or {}


def save(data):
    """写回 config.json（保留 _说明 字段）"""
    try:
        CONFIG_FILE.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return True
    except Exception:
        return False


# ---------------------------------------------------------------- 探测
def detect_profile():
    """找 DSH profile 目录。
    优先级：config → ~/.dsh/profiles/desktop → ~/.dsh/profiles 下第一个含 package.json 的"""
    c = load().get("profile")
    if c:
        p = Path(os.path.expandvars(os.path.expanduser(str(c))))
        if p.exists():
            return p, "config.json"
        return None, "config.json 里的 profile 不存在：%s" % p

    # 默认：~/.dsh/profiles/desktop
    home = Path(os.path.expanduser("~"))
    base = home / ".dsh" / "profiles"
    preferred = base / "desktop"
    if (preferred / "package.json").exists():
        return preferred, "自动探测（~/.dsh/profiles/desktop）"

    # 退而求其次：profiles 下第一个有 package.json 的
    if base.exists():
        for d in sorted(base.iterdir()):
            if d.is_dir() and (d / "package.json").exists():
                return d, "自动探测（%s）" % d.name

    return None, "找不到 DSH profile（试过 %s）" % base


def detect_dsh_roots():
    """找 DSH 安装目录候选"""
    c = load().get("dshRoots")
    if c:
        return [Path(os.path.expandvars(os.path.expanduser(str(x)))) for x in c]
    return [Path(x) for x in DEFAULT_DSH_ROOTS]


def find_dsh_root():
    """在候选里找真正装着 DeepSeek Harness.exe 的那个"""
    for r in detect_dsh_roots():
        try:
            if (r / "DeepSeek Harness.exe").exists():
                return r
        except Exception:
            pass
    return None


def detect_backup_root():
    """备份目录：config 写了用它，否则放程序目录下 _backups"""
    c = load().get("backupRoot")
    if c:
        return Path(os.path.expandvars(os.path.expanduser(str(c))))
    return APP_DIR / "_backups"


def detect_ledger():
    """台账路径。null = 未配置（开源版默认，不启用台账同步）"""
    c = load().get("ledgerPath")
    if not c:
        return None
    p = Path(os.path.expandvars(os.path.expanduser(str(c))))
    return p if p.exists() else None


def registry():
    return load().get("registry") or "https://registry.npmmirror.com"


def keep_backups():
    n = load().get("keepBackups")
    try:
        return max(1, int(n))
    except Exception:
        return 3


# ---------------------------------------------------------------- 首次运行
def ensure_config():
    """首次运行时，如果 config.json 不存在就写一份带自动探测结果的。
    返回 (config_dict, 说明文字)"""
    if not CONFIG_FILE.exists():
        prof, how = detect_profile()
        root = find_dsh_root()
        data = {
            "_说明": "插件管家配置。留空/写 null 的项会自动探测。",
            "_版本": 1,
            "profile": str(prof) if prof else None,
            "dshRoots": [str(root)] if root else None,
            "backupRoot": None,
            "ledgerPath": None,
            "registry": "https://registry.npmmirror.com",
            "keepBackups": 3,
        }
        save(data)
        return data, "已生成 config.json（profile: %s）" % how
    return load(), ""


def summary():
    """给人看的配置摘要（界面显示用）"""
    prof, prof_how = detect_profile()
    root = find_dsh_root()
    bk = detect_backup_root()
    lg = detect_ledger()
    return {
        "profile": str(prof) if prof else None,
        "profileHow": prof_how,
        "dshRoot": str(root) if root else None,
        "backupRoot": str(bk),
        "ledger": str(lg) if lg else None,
        "ledgerEnabled": lg is not None,
        "registry": registry(),
        "keepBackups": keep_backups(),
        "configFile": str(CONFIG_FILE),
    }
