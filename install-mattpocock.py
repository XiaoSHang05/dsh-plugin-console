# -*- coding: utf-8 -*-
"""
安装 mattpocock/skills 到 DSH 技能目录

它**不是 DSH 插件**（package.json 没有 dsh 字段），而是 Claude Code 格式的
技能包 —— 但内核是一样的：每个技能一个目录 + SKILL.md（YAML frontmatter）。

所以装法是：把 SKILL.md 复制到 ~/.dsh/skills/<名字>/
不是 pnpm add，不是 bundles。

用法：
    python install-mattpocock.py              # 装推荐的（排除依赖子智能体的）
    python install-mattpocock.py --all        # 装全部
    python install-mattpocock.py --list       # 只列清单
    python install-mattpocock.py --uninstall  # 全部删掉
"""

import io
import json
import shutil
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

GH = r"D:\大鲸鱼的工作间\工具仓库\gh-2.101.0\bin\gh.exe"
DSH_SKILLS = Path.home() / ".dsh" / "skills"
MARKER = "_mattpocock"          # 记录装了哪些，方便卸载

# 默认装这些（排除依赖子智能体 / issue tracker 的）
RECOMMENDED = [
    "tdd",
    "diagnosing-bugs",
    "domain-modeling",
    "to-spec",
    "to-tickets",
    "implement",
    "triage",
    "improve-codebase-architecture",
    "research",
    "prototype",
    "retro",
    "wayfinder",
]

# 明确排除（写了原因，将来想装可以手动加）
EXCLUDED = {
    "code-review": "要开并行子智能体（本机已全局禁用 maxDepth=0）",
    "ask-matt": "作者私人问答技能",
    "grill-with-docs": "要接他的 issue tracker",
    "setup-matt-pocock-skills": "安装引导，装完就没用了",
    "pr": "要接 GitHub PR 流程",
    "implement-spec": "与 implement 重复",
}


def log(s=""):
    print(s, flush=True)


def gh_api(endpoint):
    p = subprocess.run([GH, "api", endpoint], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=120)
    if p.returncode != 0:
        return None
    try:
        return json.loads(p.stdout)
    except Exception:
        return None


def list_skills():
    """列出仓库里所有技能名 + 所在分类"""
    out = []
    for cat in ("engineering", "productivity", "misc"):
        arr = gh_api(f"repos/mattpocock/skills/contents/skills/{cat}")
        if not isinstance(arr, list):
            continue
        for item in arr:
            if item.get("type") == "dir":
                out.append((item["name"], cat))
    return out


def download_zip(tmp: Path):
    """整包下载（比逐个文件取快）"""
    url = "repos/mattpocock/skills/zipball/main"
    dst = tmp / "skills.zip"
    with open(dst, "wb") as f:
        p = subprocess.run([GH, "api", url], stdout=f, stderr=subprocess.PIPE,
                           timeout=300)
    if p.returncode != 0 or dst.stat().st_size < 1000:
        return None
    return dst


def find_skill_dirs(root: Path):
    """在解压出来的树里找所有含 SKILL.md 的目录"""
    found = {}
    for sk in root.rglob("SKILL.md"):
        d = sk.parent
        # 只在 skills/<分类>/<名字>/ 这一层
        parts = d.parts
        if len(parts) >= 3 and parts[-3] == "skills" and parts[-2] in ("engineering", "productivity", "misc"):
            found[d.name] = d
    return found


def do_install(want_all=False, list_only=False):
    log("=== mattpocock/skills → DSH 技能 ===")
    log(f"目标目录: {DSH_SKILLS}")
    log()

    avail = list_skills()
    if not avail:
        log("✗ 拿不到技能清单（网络或 gh 有问题）")
        return 1

    names = [n for n, _ in avail]
    log(f"仓库里共 {len(names)} 个技能")

    if list_only:
        for n, cat in avail:
            mark = ""
            if n in EXCLUDED:
                mark = f"   ⛔ 排除：{EXCLUDED[n]}"
            elif n in RECOMMENDED:
                mark = "   ✅ 推荐"
            log(f"  [{cat:12s}] {n}{mark}")
        return 0

    if want_all:
        targets = [n for n in names if n not in EXCLUDED]
    else:
        targets = [n for n in RECOMMENDED if n in names]

    log(f"准备装 {len(targets)} 个:")
    for t in targets:
        log(f"  · {t}")
    log()

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        log("下载中…")
        z = download_zip(tmp)
        if not z:
            log("✗ 下载失败")
            return 1
        log(f"  已下载 {z.stat().st_size // 1024} KB")

        log("解压中…")
        ex = tmp / "x"
        ex.mkdir()
        with zipfile.ZipFile(z) as zf:
            zf.extractall(ex)
        # GitHub zipball 有一个顶层目录
        tops = [p for p in ex.iterdir() if p.is_dir()]
        root = tops[0] if tops else ex
        log(f"  解压到 {root.name}")

        skdirs = find_skill_dirs(root)
        log(f"  找到 {len(skdirs)} 个含 SKILL.md 的目录")
        log()

        DSH_SKILLS.mkdir(parents=True, exist_ok=True)
        installed = []
        skipped = []

        for name in targets:
            src = skdirs.get(name)
            if not src:
                skipped.append((name, "仓库里没找到"))
                continue
            dst = DSH_SKILLS / name
            if dst.exists():
                shutil.rmtree(dst, ignore_errors=True)
            shutil.copytree(src, dst)
            installed.append(name)
            log(f"  ✓ {name}")

        for n, why in skipped:
            log(f"  ✗ {n}  ({why})")

        # 记录清单
        rec = DSH_SKILLS / MARKER
        rec.mkdir(exist_ok=True)
        (rec / "installed.json").write_text(
            json.dumps({"source": "mattpocock/skills", "skills": installed},
                       ensure_ascii=False, indent=2),
            encoding="utf-8")

    log()
    log(f"=== 完成：装了 {len(installed)} 个 ===")
    log(f"记录文件: {DSH_SKILLS / MARKER / 'installed.json'}")
    log()
    log("★ 技能是纯 markdown，不用重启 DSH 就能用。")
    log("  下次我遇到对应场景会自动加载（或你说「用 tdd 技能」）。")
    return 0


def do_uninstall():
    rec = DSH_SKILLS / MARKER / "installed.json"
    if not rec.exists():
        log("没找到安装记录，不知道怎么删。")
        log(f"（记录应在这里: {rec}）")
        return 1
    data = json.loads(rec.read_text(encoding="utf-8"))
    skills = data.get("skills") or []
    log(f"=== 卸载 {len(skills)} 个技能 ===")
    n = 0
    for s in skills:
        d = DSH_SKILLS / s
        if d.exists():
            shutil.rmtree(d, ignore_errors=True)
            log(f"  ✓ 删除 {s}")
            n += 1
    shutil.rmtree(DSH_SKILLS / MARKER, ignore_errors=True)
    log(f"\n共删除 {n} 个")
    return 0


def main():
    args = sys.argv[1:]
    if "--uninstall" in args:
        return do_uninstall()
    if "--list" in args:
        return do_install(list_only=True)
    return do_install(want_all="--all" in args)


if __name__ == "__main__":
    sys.exit(main())
