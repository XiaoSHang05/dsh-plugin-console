# -*- coding: utf-8 -*-
"""
插件管家 · Python 后端

前端是 index.html（HTML/CSS/JS），后端负责所有真实操作。
pywebview 的 js_api 会把这些方法暴露给 window.pywebview.api。

铁律（都是踩出来的）：
  1. DSH 运行中 ⇒ 一切写操作拒绝（改 node_modules 会把活进程搞崩）
  2. pnpm add/remove 之前，先把 link:/git+ 依赖临时摘出去（否则会去连 GitHub）
  3. 装完必须挂进 dsh.profile.bundles（否则装了也看不见，且不报错）
  4. 任何写操作前先备份；备份最多留 3 份
"""

import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request

import ledger as ledger_mod
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------- 常量
# ★ 2026-10-29：路径不再写死，全部走 paths.py（读 config.json + 自动探测）
#    这样自用版和开源版是同一份代码，只是 config.json 不同。
import paths as _paths

_profile_dir, _profile_how = _paths.detect_profile()
if _profile_dir is None:
    raise RuntimeError("找不到 DSH profile：%s（请编辑 config.json）" % _profile_how)

PROFILE = _profile_dir
BACKUP_ROOT = _paths.detect_backup_root()
DSH_ROOTS = _paths.detect_dsh_roots()
REGISTRY = _paths.registry()
NON_REGISTRY = re.compile(
    r"^(link:|file:|portal:|github:|git\+|git:|https?:|workspace:|npm:)", re.I
)
KEEP_BACKUPS = _paths.keep_backups()


# ---------------------------------------------------------------- 基础探测
def find_dsh_root():
    for r in DSH_ROOTS:
        try:
            if (r / "DeepSeek Harness.exe").exists():
                return r
        except OSError:
            pass
    return None


def dsh_version(root):
    """读 asar 外面的 package.json；退化到 exe 版本信息"""
    if not root:
        return None
    for rel in ("resources/app/package.json", "resources/app.asar/package.json"):
        try:
            with open(root / rel, encoding="utf-8") as f:
                v = json.load(f).get("version")
            if v:
                return v
        except Exception:
            pass
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             f"(Get-Item '{root / 'DeepSeek Harness.exe'}').VersionInfo.FileVersion"],
            capture_output=True, text=True, timeout=8,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        ).stdout.strip()
        if re.match(r"^\d+\.\d+\.\d+", out):
            return out
    except Exception:
        pass
    return None


def dsh_process_count():
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "(Get-Process -Name 'DeepSeek Harness' -ErrorAction SilentlyContinue | Measure-Object).Count"],
            capture_output=True, text=True, timeout=8,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        ).stdout.strip()
        n = int(out or "0")
        return n if n > 0 else 0
    except Exception:
        return 0


# ---------------------------------------------------------------- 读本地状态
def read_profile():
    pj_path = PROFILE / "package.json"
    with open(pj_path, encoding="utf-8") as f:
        pj = json.load(f)
    return pj, pj_path, pj.get("dependencies", {}), pj.get("dsh", {}).get("profile", {}).get("bundles", [])


def local_version(name):
    try:
        with open(PROFILE / "node_modules" / name / "package.json", encoding="utf-8") as f:
            return json.load(f).get("version")
    except Exception:
        return None


def local_pkg_json(name):
    try:
        with open(PROFILE / "node_modules" / name / "package.json", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def local_description(name):
    return str(local_pkg_json(name).get("description") or "").strip()


def local_dsh_range(name):
    j = local_pkg_json(name)
    return (
        j.get("dsh", {}).get("compatibility", {}).get("dsh")
        or j.get("engines", {}).get("dsh")
        or ""
    )


def has_bundle_patch(name):
    j = local_pkg_json(name)
    return bool(j.get("dsh", {}).get("bundle", {}).get("patch"))


# ---------------------------------------------------------------- changelog
CL_FILES = ["CHANGELOG.zh-CN.md", "CHANGELOG.md", "changelog.md",
            "CHANGES.md", "HISTORY.md", "RELEASES.md"]


def read_changelog(name, version):
    """取某版本的 changelog 要点，最多 3 条"""
    d = PROFILE / "node_modules" / name
    raw = None
    for f in CL_FILES:
        p = d / f
        if p.is_file():
            try:
                raw = p.read_text(encoding="utf-8", errors="replace")
                break
            except Exception:
                pass
    if not raw:
        return None

    lines = raw.splitlines()
    esc = re.escape(version)
    head_re = re.compile(rf"^#{{1,3}}\s*\[?v?{esc}\]?\b", re.I)
    start = next((i for i, l in enumerate(lines) if head_re.match(l.strip())), -1)
    if start < 0:
        return None

    level = len(re.match(r"^#+", lines[start]).group(0))
    end = len(lines)
    for i in range(start + 1, len(lines)):
        m = re.match(r"^(#+)\s", lines[i])
        if m and len(m.group(1)) <= level:
            end = i
            break

    items, cur = [], ""
    for raw_l in lines[start + 1:end]:
        t = raw_l.strip()
        if not t:
            if cur:
                items.append(cur)
                cur = ""
            continue
        if re.match(r"^#{1,6}\s", t) or re.match(r"^\*\*[^*]{1,40}\*\*:?$", t):
            if cur:
                items.append(cur)
                cur = ""
            continue
        clean = re.sub(r"^[-*+]\s+", "", t)
        clean = re.sub(r"^\d+[.)]\s+", "", clean)
        clean = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", clean)
        clean = clean.replace("`", "").replace("**", "").replace("__", "")
        if not clean.strip():
            continue
        if re.match(r"^[-*+]\s+", t) or re.match(r"^\d+[.)]\s+", t):
            if cur:
                items.append(cur)
            cur = clean.strip()
        elif cur:
            cur += " " + clean.strip()
        else:
            cur = clean.strip()
        if len(items) > 14:
            break
    if cur:
        items.append(cur)

    skip_re = re.compile(r"^(first (public )?release|initial (public )?release|首次发布|初始版本)[.。!！]?$", re.I)
    useful = []
    for s in items:
        s = s.strip()
        if not s or len(s) <= 6:
            continue
        if re.match(r"^\d{4}-\d{2}-\d{2}$", s) or s.startswith("http"):
            continue
        if skip_re.match(s):
            continue
        if len(s) > 88:
            s = s[:87] + "…"
        useful.append(s)
    return useful[:3] or None


# ---------------------------------------------------------------- semver
_VER_RE = re.compile(r"^v?(\d+)(?:\.(\d+))?(?:\.(\d+))?(?:-([0-9A-Za-z.-]+))?$")


def parse_ver(v):
    m = _VER_RE.match(str(v).strip())
    if not m:
        return None
    return {
        "maj": int(m.group(1)),
        "min": int(m.group(2) or 0),
        "pat": int(m.group(3) or 0),
        "pre": (m.group(4) or "").split(".") if m.group(4) else [],
    }


def _cmp_pre(a, b):
    if not a and not b:
        return 0
    if not a:
        return 1
    if not b:
        return -1
    for i in range(max(len(a), len(b))):
        if i >= len(a):
            return -1
        if i >= len(b):
            return 1
        x, y = a[i], b[i]
        nx, ny = x.isdigit(), y.isdigit()
        if nx and ny:
            if int(x) != int(y):
                return -1 if int(x) < int(y) else 1
        elif nx:
            return -1
        elif ny:
            return 1
        elif x != y:
            return -1 if x < y else 1
    return 0


def _cmp_ver(a, b):
    for k in ("maj", "min", "pat"):
        if a[k] != b[k]:
            return -1 if a[k] < b[k] else 1
    return _cmp_pre(a["pre"], b["pre"])


def satisfies(ver, rng):
    """True / False / None(无法判定)"""
    if not rng:
        return None
    vp = parse_ver(ver)
    if not vp:
        return None
    for alt in [s.strip() for s in str(rng).split("||") if s.strip()]:
        if re.search(r"[\^~*x]", alt):
            return None
        ok = True
        for p in alt.split():
            m = re.match(r"^(>=|<=|>|<|=)?\s*(.+)$", p)
            if not m:
                ok = False
                break
            op = m.group(1) or "="
            bp = parse_ver(m.group(2))
            if not bp:
                ok = False
                break
            c = _cmp_ver(vp, bp)
            passed = (
                c >= 0 if op == ">=" else
                c <= 0 if op == "<=" else
                c > 0 if op == ">" else
                c < 0 if op == "<" else
                c == 0
            )
            if not passed:
                ok = False
                break
        if ok:
            return True
    return False


def version_jump(frm, to):
    a, b = parse_ver(frm or ""), parse_ver(to or "")
    if not a or not b:
        return None
    if b["maj"] != a["maj"]:
        return {"kind": "major", "label": "大版本", "hint": "可能有破坏性改动"}
    if b["min"] != a["min"]:
        n = b["min"] - a["min"]
        return {"kind": "minor", "label": "功能级", "hint": "新增了功能" if n == 1 else f"跨 {n} 个功能版本"}
    if b["pat"] != a["pat"]:
        n = b["pat"] - a["pat"]
        return {"kind": "patch", "label": "补丁级", "hint": "以修 bug 为主" if n == 1 else f"跨 {n} 个补丁"}
    return {"kind": "same", "label": "同版本", "hint": "版本号没变"}


# ---------------------------------------------------------------- 云端
def fetch_latest(name):
    url = f"{REGISTRY}/{urllib.parse.quote(name, safe='')}/latest"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "shizhen-plugin-console/1.0"})
        with urllib.request.urlopen(req, timeout=20) as r:
            j = json.load(r)
        return {
            "version": j.get("version"),
            "engines": j.get("engines") or {},
            "description": str(j.get("description") or "").strip(),
            "dshRange": (j.get("dsh", {}).get("compatibility", {}).get("dsh")
                         or (j.get("engines") or {}).get("dsh") or ""),
        }
    except Exception as e:
        return {"err": str(e)[:70]}


# ---------------------------------------------------------------- 主查询
def scan_all(on_progress=None):
    root = find_dsh_root()
    dsh_ver = dsh_version(root)
    running = dsh_process_count()
    pj, _, deps, bundles = read_profile()
    names = list(deps.keys())

    rows = []
    for i, name in enumerate(names, 1):
        if on_progress:
            on_progress(i, len(names), name)

        spec = str(deps[name])
        cur = local_version(name)
        mounted = name in bundles

        if NON_REGISTRY.match(spec):
            rows.append({
                "name": name, "cur": cur, "latest": None, "verdict": "LOCAL",
                "mounted": mounted, "desc": local_description(name),
                "note": "本地/git 来源，不参与更新", "kind": "local",
                "jumpLabel": "", "jumpHint": "",
            })
            continue

        r = fetch_latest(name)
        if r.get("err"):
            rows.append({
                "name": name, "cur": cur, "latest": None, "verdict": "ERR",
                "mounted": mounted, "desc": local_description(name),
                "note": r["err"], "kind": "err", "jumpLabel": "", "jumpHint": "",
            })
            continue

        eff_cur = cur or (spec if parse_ver(spec) else None)
        if eff_cur == r["version"]:
            rows.append({
                "name": name, "cur": eff_cur, "latest": r["version"], "verdict": "OK",
                "mounted": mounted,
                "desc": local_description(name) or r["description"],
                "note": "已是最新", "kind": "ok", "jumpLabel": "", "jumpHint": "",
            })
            continue

        verdict, note = "UPDATE", ""
        rng = r.get("dshRange") or ""
        if rng and dsh_ver:
            s = satisfies(dsh_ver, rng)
            if s is False:
                verdict = "SKIP"
                note = f"需要 dsh {rng}，当前 {dsh_ver}"
            elif s is None:
                note = f"dsh 约束「{rng}」含 ^~，放行"
            else:
                note = f"兼容 dsh {dsh_ver}"
        else:
            note = "未识别当前内核" if rng else "未声明 dsh 约束，放行"

        node_rng = r.get("engines", {}).get("node")
        if node_rng:
            s2 = satisfies(".".join(map(str, sys.version_info[:3])), node_rng)
            if s2 is False:
                verdict = "SKIP"
                note = f"需要 node {node_rng}"

        jump = version_jump(eff_cur, r["version"])
        rows.append({
            "name": name, "cur": eff_cur, "latest": r["version"], "verdict": verdict,
            "mounted": mounted,
            "desc": local_description(name) or r["description"],
            "note": note,
            "kind": jump["kind"] if jump else "patch",
            "jumpLabel": jump["label"] if jump else "",
            "jumpHint": jump["hint"] if jump else "",
        })

    # ★ 排序：可更新的排最前（宴城 2026-10-29 要求）
    #   优先级：UPDATE > SKIP > ERR > OK > LOCAL
    _order = {"UPDATE": 0, "SKIP": 1, "ERR": 2, "OK": 3, "LOCAL": 4}
    rows.sort(key=lambda r: (_order.get(r["verdict"], 9), r["name"].lower()))

    return {"rows": rows, "dshRunning": running, "dshVer": dsh_ver,
            "root": str(root) if root else None}


# ---------------------------------------------------------------- 备份
def make_backup(kind):
    ts = datetime.now().strftime("%Y%m%d%H%M%S")
    d = BACKUP_ROOT / kind / ts
    d.mkdir(parents=True, exist_ok=True)
    for f in ("package.json", "pnpm-lock.yaml", "pnpm-workspace.yaml"):
        src = PROFILE / f
        if src.exists():
            try:
                shutil.copy2(src, d / f)
            except Exception:
                pass
    # 轮转
    try:
        root = BACKUP_ROOT / kind
        dirs = sorted([p.name for p in root.iterdir()
                       if p.is_dir() and re.match(r"^\d{14}", p.name)])
        for old in dirs[:max(0, len(dirs) - KEEP_BACKUPS)]:
            shutil.rmtree(root / old, ignore_errors=True)
    except Exception:
        pass
    return str(d)


def list_backups(kind="update"):
    d = BACKUP_ROOT / kind
    if not d.exists():
        return []
    out = []
    for p in sorted(d.iterdir(), reverse=True):
        if p.is_dir() and re.match(r"^\d{14}", p.name):
            n = p.name
            out.append({
                "id": n,
                "at": f"{n[0:4]}-{n[4:6]}-{n[6:8]} {n[8:10]}:{n[10:12]}:{n[12:14]}",
            })
    return out


# ---------------------------------------------------------------- pnpm
def pnpm_path():
    root = find_dsh_root()
    if not root:
        return None
    p = root / "resources/runtime/primary-runtime/dependencies/pnpm/bin/pnpm.cjs"
    return p if p.exists() else None


def park_non_registry():
    """把 link:/git+ 依赖临时摘出，返回 (count, restore_fn)"""
    pj_path = PROFILE / "package.json"
    with open(pj_path, encoding="utf-8") as f:
        pj = json.load(f)
    deps = pj.get("dependencies", {})
    parked = [(n, s) for n, s in deps.items() if NON_REGISTRY.match(str(s))]
    if not parked:
        return 0, lambda: None
    for n, _ in parked:
        deps.pop(n, None)
    with open(pj_path, "w", encoding="utf-8") as f:
        json.dump(pj, f, ensure_ascii=False, indent=2)
        f.write("\n")

    def restore():
        try:
            with open(pj_path, encoding="utf-8") as f:
                now = json.load(f)
            now.setdefault("dependencies", {})
            for n, s in parked:
                now["dependencies"][n] = s
            with open(pj_path, "w", encoding="utf-8") as f:
                json.dump(now, f, ensure_ascii=False, indent=2)
                f.write("\n")
        except Exception:
            pass

    return len(parked), restore


def run_pnpm(args, on_line):
    """跑 pnpm，逐行回调"""
    pnpm = pnpm_path()
    if not pnpm:
        on_line("找不到 pnpm.cjs")
        return 1
    cmd = [sys.executable if False else "node", str(pnpm)] + args + ["--config.confirmModulesPurge=false"]
    # 用本机 node（DSH 自带的不一定在 PATH，退化到 python 所在目录旁）
    node_exe = shutil.which("node") or r"E:\Node.js\node.exe"
    cmd = [node_exe, str(pnpm)] + args + ["--config.confirmModulesPurge=false"]
    try:
        p = subprocess.Popen(
            cmd, cwd=str(PROFILE), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace", bufsize=1,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        for line in p.stdout:
            on_line(line.rstrip())
        p.wait()
        return p.returncode or 0
    except Exception as e:
        on_line(f"执行失败：{e}")
        return 1


def mount_bundles(names, on_log):
    """把包挂进 bundles（只挂声明了 bundle.patch 的）"""
    pj_path = PROFILE / "package.json"
    with open(pj_path, encoding="utf-8") as f:
        pj = json.load(f)
    pj.setdefault("dsh", {}).setdefault("profile", {}).setdefault("bundles", [])
    bl = pj["dsh"]["profile"]["bundles"]
    before = len(bl)
    added = []
    for n in names:
        if not has_bundle_patch(n):
            continue
        if n not in bl:
            bl.append(n)
            added.append(n)
    if added:
        with open(pj_path, "w", encoding="utf-8") as f:
            json.dump(pj, f, ensure_ascii=False, indent=2)
            f.write("\n")
        on_log(f"已挂进 bundles：{before} → {len(bl)}（{', '.join(added)}）")
    return added


def unmount_bundles(names):
    pj_path = PROFILE / "package.json"
    with open(pj_path, encoding="utf-8") as f:
        pj = json.load(f)
    bl = pj.get("dsh", {}).get("profile", {}).get("bundles", [])
    before = len(bl)
    removed = [b for b in bl if b in names]
    if removed:
        pj["dsh"]["profile"]["bundles"] = [b for b in bl if b not in names]
        with open(pj_path, "w", encoding="utf-8") as f:
            json.dump(pj, f, ensure_ascii=False, indent=2)
            f.write("\n")
    return removed, before, len(pj.get("dsh", {}).get("profile", {}).get("bundles", []))


def add_whitelist(names_versions):
    """把目标版本写进 minimumReleaseAgeExclude（避开下载冷静期）"""
    ws = PROFILE / "pnpm-workspace.yaml"
    if not ws.exists():
        return
    try:
        text = ws.read_text(encoding="utf-8")
        changed = False
        for nv in names_versions:
            if nv in text:
                continue
            m = re.search(r"minimumReleaseAgeExclude:\s*\n((?:\s+-\s+.*\n)*)", text)
            if not m:
                continue
            idx = m.end()
            text = text[:idx] + f"  - '{nv}'\n" + text[idx:]
            changed = True
        if changed:
            ws.write_text(text, encoding="utf-8")
    except Exception:
        pass


# ---------------------------------------------------------------- 台账中文说明
LEDGER = Path("D:/大鲸鱼的工作间/AI-ku/40-DSH插件管理/DSH插件台账.md")


DESC_FILE = Path(__file__).parent / "descriptions.json"


def read_builtin_descriptions():
    """读软件自带的中文说明词典 descriptions.json。
    这是「通用能力」——开源版也带着它，别人的软件也有中文说明。"""
    if not DESC_FILE.exists():
        return {}
    try:
        data = json.loads(DESC_FILE.read_text(encoding="utf-8"))
        d = data.get("descriptions") or {}
        return {str(k): str(v) for k, v in d.items() if k and v}
    except Exception:
        return {}


def read_ledger_descriptions():
    """从 DSH插件台账.md 读中文说明（**私有增强**）。
    台账不存在时返回空 dict，不影响自带词典。"""
    if not LEDGER.exists():
        return {}
    try:
        text = LEDGER.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return {}

    lines = text.splitlines()
    start = None
    for i, l in enumerate(lines):
        if re.match(r"^\|\s*插件\s*\|\s*干什么的\s*\|", l):
            start = i
            break
    if start is None:
        return {}

    out = {}
    for l in lines[start + 2:]:
        if not l.startswith("|"):
            break
        cells = [c.strip() for c in l.strip("|").split("|")]
        if len(cells) < 2:
            continue
        name = cells[0]
        desc = cells[1]
        # 清洗 markdown：去加粗、去 🆕、去括号补充
        name = name.replace("**", "")
        name = re.sub(r"^🆕\s*", "", name)
        name = re.sub(r"（[^）]*）", "", name).strip()
        desc = desc.replace("**", "").strip()
        if not name or not desc:
            continue
        # 只取第一句（台账说明常很长，界面里够用了）
        first = re.split(r"[；;]", desc)[0].strip()
        out[name] = first if first else desc
    return out


# ---------------------------------------------------------------- 列全部已装
# ---------------------------------------------------------------- 分类
CATEGORY_FILE = Path(__file__).parent / "categories.json"
_cat_cache = {"mtime": 0, "data": None}


def load_categories():
    """读 categories.json；文件变了就重载。"""
    try:
        mtime = CATEGORY_FILE.stat().st_mtime
    except Exception:
        return None
    if _cat_cache["data"] is not None and _cat_cache["mtime"] == mtime:
        return _cat_cache["data"]
    try:
        data = json.loads(CATEGORY_FILE.read_text(encoding="utf-8"))
        _cat_cache["data"] = data
        _cat_cache["mtime"] = mtime
        return data
    except Exception:
        return _cat_cache["data"]


def all_descriptions():
    """中文说明的**统一入口**。
    优先级：台账（私有增强，能随时改） > 自带词典（通用，开源版也有）
    两者都没有时，上层会退回 package.json 的描述。"""
    out = dict(read_builtin_descriptions())   # ① 软件自带（通用）
    try:
        out.update(read_ledger_descriptions())  # ② 台账覆盖（私有）
    except Exception:
        pass
    return out


def classify(name, desc, cats=None):
    """加权打分分类：每条规则都算分，取最高分（不是「第一个命中」）。
       返回 (分类id, 分数)。分数 0 表示没命中任何规则 → other。"""
    if cats is None:
        cats = load_categories()
    if not cats:
        return "other", 0

    # ① 手动指定优先
    ov = cats.get("overrides") or {}
    if name in ov:
        return ov[name], 999

    blob = (str(name) + " " + str(desc or "")).lower()
    best_id, best_score = "other", 0
    for c in cats.get("categories", []):
        if c.get("id") == "other":
            continue
        score = 0
        for word, weight in (c.get("keywords") or {}).items():
            if word.lower() in blob:
                score += int(weight)
        if score > best_score:
            best_id, best_score = c.get("id"), score
    return best_id, best_score


def category_meta(cats=None):
    """返回 [{id,name,icon,color,desc}]"""
    if cats is None:
        cats = load_categories()
    if not cats:
        return []
    return [{
        "id": c.get("id"),
        "name": c.get("name"),
        "icon": c.get("icon"),
        "color": c.get("color"),
        "desc": c.get("desc", ""),
    } for c in cats.get("categories", [])]


# ---------------------------------------------------------------- 列全部已装
def list_installed(grouped=False):
    """返回全部已装插件 + 中文说明 + 版本 + 挂载状态。
       grouped=True 时额外按分类分组，并给每类统计。"""
    try:
        pj, _, deps, bundles = read_profile()
    except Exception as e:
        return {"ok": False, "error": str(e)}

    descs = all_descriptions()
    cats = load_categories()
    meta = category_meta(cats)
    meta_by_id = {m["id"]: m for m in meta}

    rows = []
    for name, spec in deps.items():
        ver = local_version(name)
        is_local = bool(NON_REGISTRY.match(str(spec)))
        mounted = name in bundles
        desc = descs.get(name) or local_description(name) or ""
        cid, score = classify(name, desc, cats)
        m = meta_by_id.get(cid) or {"name": "其他", "color": "#64748b", "icon": "box"}
        rows.append({
            "name": name,
            "version": ver,
            "spec": str(spec),
            "isLocal": is_local,
            "mounted": mounted,
            "hasBundle": has_bundle_patch(name),
            "desc": desc,
            "fromLedger": name in descs,
            "cat": cid,
            "catName": m["name"],
            "catColor": m["color"],
            "catIcon": m["icon"],
            "catScore": score,
        })

    rows.sort(key=lambda r: (r["catName"], not r["mounted"], r["name"].lower()))

    out = {
        "ok": True,
        "rows": rows,
        "total": len(rows),
        "mounted": sum(1 for r in rows if r["mounted"]),
        "local": sum(1 for r in rows if r["isLocal"]),
        "fromLedger": sum(1 for r in rows if r["fromLedger"]),
        "categories": meta,
    }

    if grouped:
        groups = {}
        for r in rows:
            groups.setdefault(r["cat"], []).append(r)
        # 按 categories 定义的顺序输出，空的跳过
        ordered = []
        for m in meta:
            items = groups.get(m["id"])
            if not items:
                continue
            ordered.append({
                **m,
                "count": len(items),
                "mounted": sum(1 for x in items if x["mounted"]),
                "items": items,
            })
        out["groups"] = ordered

    return out


# ---------------------------------------------------------------- 台账同步
_ledger_bound = False


def _ensure_ledger():
    global _ledger_bound
    if not _ledger_bound:
        ledger_mod.bind(PROFILE, BACKUP_ROOT, local_version, read_profile)
        _ledger_bound = True


def sync_ledger(on_log=None):
    """把真实版本号写回台账（§一 版本格 + §七 更新记录）"""
    try:
        _ensure_ledger()
        return ledger_mod.sync(on_log)
    except Exception as e:
        return {"ok": False, "error": str(e)}


def dedupe_whitelist(on_log=None):
    """清掉 pnpm-workspace.yaml 里 minimumReleaseAgeExclude 的重复规则"""
    ws = PROFILE / "pnpm-workspace.yaml"
    if not ws.exists():
        return {"ok": False, "error": "没有 pnpm-workspace.yaml"}
    try:
        text = ws.read_text(encoding="utf-8")
    except Exception as e:
        return {"ok": False, "error": str(e)}

    lines = text.split("\n")
    key = None
    for i, l in enumerate(lines):
        if l.strip() == "minimumReleaseAgeExclude:":
            key = i
            break
    if key is None:
        return {"ok": False, "error": "没找到 minimumReleaseAgeExclude"}

    start = key + 1
    end = start
    while end < len(lines) and re.match(r"^\s+-\s", lines[end]):
        end += 1

    seen = set()
    kept = []
    removed = 0
    for l in lines[start:end]:
        body = re.sub(r"^\s+-\s*", "", l).strip().strip("'\"")
        if body in seen:
            removed += 1
            continue
        seen.add(body)
        kept.append(l)

    if removed == 0:
        return {"ok": True, "removed": 0}

    lines[start:end] = kept
    ws.write_text("\n".join(lines), encoding="utf-8")
    if on_log:
        on_log("白名单去重：删掉 %d 条重复规则" % removed)
    return {"ok": True, "removed": removed}


# ---------------------------------------------------------------- 对外 API
def do_update(names, on_log, on_progress=None):
    if dsh_process_count() > 0:
        return {"ok": False, "error": "DSH 正在运行，不能更新"}

    sc = scan_all()
    targets = [r for r in sc["rows"] if r["name"] in names and r["verdict"] == "UPDATE"]
    if not targets:
        return {"ok": False, "error": "没有可更新的目标"}

    backup_dir = make_backup("update")
    on_log(f"已备份到 {backup_dir}")

    parked, restore = park_non_registry()
    if parked:
        on_log(f"临时摘出 {parked} 个本地/git 依赖（避免 pnpm 去连 GitHub）")

    add_whitelist([f"{t['name']}@{t['latest']}" for t in targets])

    results = []
    for i, t in enumerate(targets, 1):
        if on_progress:
            on_progress(i, len(targets), t["name"])
        on_log(f"\n[{i}/{len(targets)}] {t['name']}@{t['latest']}")
        code = run_pnpm(["add", f"{t['name']}@{t['latest']}", "-E"], on_log)
        now = local_version(t["name"])
        ok = now == t["latest"]
        results.append({"name": t["name"], "from": t["cur"], "to": now, "ok": ok, "code": code})
        on_log(f"{'✓' if ok else '✗'} {t['name']} → {now or '读不到'}")

    restore()
    if parked:
        on_log(f"已把 {parked} 个本地/git 依赖放回")

    added = mount_bundles([t["name"] for t in targets], on_log)

    notes = []
    for r in [x for x in results if x["ok"]]:
        notes.append({
            "name": r["name"], "from": r["from"], "to": r["to"],
            "jump": version_jump(r["from"], r["to"]),
            "changelog": read_changelog(r["name"], r["to"] or ""),
        })

    # ★ 台账同步（宴城 2026-10-26 要求）：把真实版本写回 DSH插件台账.md
    on_log("")
    on_log("──────── 台账同步 ────────")
    ledger_result = sync_ledger(on_log)
    if ledger_result.get("skipped"):
        on_log("台账不存在，跳过")
    elif not ledger_result.get("ok"):
        on_log("台账同步失败：%s" % ledger_result.get("error", ""))
    else:
        n_p = len(ledger_result.get("patched") or [])
        n_r = ledger_result.get("records") or 0
        if ledger_result.get("changed"):
            on_log("✓ 版本格更新 %d 处，追加记录 %d 行" % (n_p, n_r))
            bk = ledger_result.get("backup")
            if bk:
                on_log("  台账备份：%s" % bk)
        else:
            on_log("台账已是最新，无需改动")
        missing = ledger_result.get("missing") or []
        if missing:
            on_log("  台账里找不到 %d 个：%s" % (len(missing), ", ".join(missing[:6])))

    return {
        "ok": all(r["ok"] for r in results),
        "results": results, "notes": notes,
        "backupDir": backup_dir, "mounted": added,
        "ledger": ledger_result,
    }


def do_uninstall(names, on_log):
    if dsh_process_count() > 0:
        return {"ok": False, "error": "DSH 正在运行，不能卸载"}

    backup_dir = make_backup("uninstall")
    on_log(f"已备份到 {backup_dir}")

    parked, restore = park_non_registry()
    if parked:
        on_log(f"临时摘出 {parked} 个本地/git 依赖")

    on_log(f"正在移除：{', '.join(names)}")
    code = run_pnpm(["remove"] + list(names), on_log)
    restore()

    # 兜底清理
    pj_path = PROFILE / "package.json"
    with open(pj_path, encoding="utf-8") as f:
        pj = json.load(f)
    deps = pj.setdefault("dependencies", {})
    changed = False
    for n in names:
        if n in deps:
            deps.pop(n)
            changed = True
    if changed:
        with open(pj_path, "w", encoding="utf-8") as f:
            json.dump(pj, f, ensure_ascii=False, indent=2)
            f.write("\n")
    unmount_bundles(names)

    with open(pj_path, encoding="utf-8") as f:
        pj2 = json.load(f)
    bl = pj2.get("dsh", {}).get("profile", {}).get("bundles", [])
    verify = [{
        "name": n,
        "inDeps": n in pj2.get("dependencies", {}),
        "inBundles": n in bl,
        "inNM": (PROFILE / "node_modules" / n).exists(),
    } for n in names]

    return {
        "ok": all((not v["inDeps"]) and (not v["inBundles"]) and (not v["inNM"]) for v in verify),
        "verify": verify, "backupDir": backup_dir, "code": code,
    }


def do_rollback(backup_id, on_log):
    if dsh_process_count() > 0:
        return {"ok": False, "error": "DSH 正在运行，不能回滚"}
    src = BACKUP_ROOT / "update" / backup_id
    if not src.exists():
        return {"ok": False, "error": "找不到这个备份"}

    safety = make_backup("rollback")
    on_log(f"当前状态已另存：{safety}")

    for f in ("package.json", "pnpm-lock.yaml"):
        if (src / f).exists():
            shutil.copy2(src / f, PROFILE / f)
            on_log(f"已恢复 {f}")

    parked, restore = park_non_registry()
    if parked:
        on_log(f"临时摘出 {parked} 个本地/git 依赖")
    on_log("正在重装依赖…")
    code = run_pnpm(["install"], on_log)
    restore()
    return {"ok": code == 0, "code": code}
