# -*- coding: utf-8 -*-
"""
插件管家 · 启动器
pywebview 把 backend 的方法暴露给前端 window.pywebview.api
"""

import json
import os
import sys
import threading
import traceback
from pathlib import Path

import webview


def _app_dir():
    """打包成 exe 后，资源解压在 sys._MEIPASS；直接跑时用脚本所在目录。
    注意：配置文件（theme.json / config.json）要写在 exe **旁边**，
    不能写进 _MEIPASS（那是临时目录，退出就没了）。"""
    if getattr(sys, "frozen", False):
        # exe 所在目录（可写）
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent


def _res_dir():
    """打包后只读资源在 _MEIPASS，开发和运行时在脚本目录"""
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return Path(meipass)
    return Path(__file__).resolve().parent


HERE = _app_dir()      # 可写目录（config/theme/backups 都在这）
RES = _res_dir()       # 只读资源（ui/ icon.ico）
THEME_FILE = HERE / "theme.json"
sys.path.insert(0, str(RES))
sys.path.insert(0, str(HERE))

import backend  # noqa: E402


class Api:
    """暴露给前端的方法集合"""

    def __init__(self):
        self._win = None
        self._lock = threading.Lock()

    def bind(self, win):
        self._win = win

    # ---------------- 环境
    def env_info(self):
        root = backend.find_dsh_root()
        return {
            "root": str(root) if root else None,
            "dshVer": backend.dsh_version(root),
            "running": backend.dsh_process_count(),
            "profile": str(backend.PROFILE),
            "backupRoot": str(backend.BACKUP_ROOT),
            "python": sys.version.split()[0],
        }

    def pulse(self):
        return {
            "running": backend.dsh_process_count(),
            "ver": backend.dsh_version(backend.find_dsh_root()),
        }

    # ---------------- 扫描
    def scan(self):
        try:
            def prog(i, total, name):
                self._emit("scan:progress", {"done": i, "total": total, "name": name})
            r = backend.scan_all(prog)
            return {"ok": True, **r}
        except Exception as e:
            traceback.print_exc()
            return {"ok": False, "error": str(e)}

    # ---------------- 动作
    def update(self, names):
        try:
            def log(s):
                self._emit("act:log", str(s))

            def prog(i, total, name):
                self._emit("act:progress", {"i": i, "total": total, "name": name})

            return backend.do_update(list(names), log, prog)
        except Exception as e:
            traceback.print_exc()
            return {"ok": False, "error": str(e)}

    def uninstall(self, names):
        try:
            def log(s):
                self._emit("act:log", str(s))
            return backend.do_uninstall(list(names), log)
        except Exception as e:
            traceback.print_exc()
            return {"ok": False, "error": str(e)}

    def rollback(self, backup_id):
        try:
            def log(s):
                self._emit("act:log", str(s))
            return backend.do_rollback(backup_id, log)
        except Exception as e:
            traceback.print_exc()
            return {"ok": False, "error": str(e)}

    def list_backups(self):
        return backend.list_backups("update")

    def open_backup_dir(self):
        try:
            os.startfile(str(backend.BACKUP_ROOT))
        except Exception as e:
            return str(e)
        return None

    def minimize(self):
        try:
            self._win.minimize()
        except Exception:
            pass

    def toggle_max(self):
        try:
            self._win.toggle_fullscreen() if False else None
        except Exception:
            pass

    # ---------------- 配置状态
    def config_summary(self):
        try:
            import paths
            return {"ok": True, **paths.summary()}
        except Exception as e:
            traceback.print_exc()
            return {"ok": False, "error": str(e)}

    def open_config(self):
        try:
            import paths
            os.startfile(str(paths.CONFIG_FILE))
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # ---------------- 添加插件：查包 / 装包
    def probe_package(self, name):
        try:
            return backend.probe_package(name)
        except Exception as e:
            traceback.print_exc()
            return {"ok": False, "error": str(e)}

    def install_package(self, name):
        try:
            n = backend.dsh_process_count()
            if n > 0:
                msg = "DSH 正在运行（%d 个进程），先彻底退出再装" % n
                return {"ok": False, "error": msg, "log": ["✗ " + msg]}

            logs = []

            def on_log(s):
                logs.append(str(s))
                self._emit("log", str(s))

            on_log("备份中…")
            backup = backend.make_backup("install")
            on_log("  → %s" % backup)

            parked, restore = backend.park_non_registry()
            if parked:
                on_log("临时摘出 %d 个本地/git 依赖" % parked)

            on_log("安装中…")
            backend.run_pnpm(["add", name, "-E"], on_log)
            restore()
            if parked:
                on_log("已放回 %d 个本地/git 依赖" % parked)

            on_log("挂 bundles…")
            base = name.split("@")[0] if name.startswith("@") else name
            # 带版本的写法要剥掉版本
            if "@" in base:
                base = base.split("@")[0]
            backend.mount_bundles([base], on_log)

            pj, _, deps, bundles = backend.read_profile()
            ver = backend.local_version(base)
            on_log("")
            on_log("──── 验证 ────")
            on_log("  版本        : %s" % (ver or "读不到"))
            on_log("  dependencies: %s" % ("Y" if base in deps else "N"))
            on_log("  bundles     : %s" % ("Y" if base in bundles else "N"))

            ok = bool(ver) and base in deps and base in bundles
            if not ok:
                on_log("✗ 有项没到位")
            return {"ok": ok, "log": logs}
        except Exception as e:
            traceback.print_exc()
            return {"ok": False, "error": str(e), "log": ["异常：%s" % e]}

    # ---------------- 已装插件（分组版）
    def list_installed_grouped(self):
        try:
            return backend.list_installed(grouped=True)
        except Exception as e:
            traceback.print_exc()
            return {"ok": False, "error": str(e)}

    # ---------------- 重新载入分类规则
    def reload_categories(self):
        try:
            backend._cat_cache["data"] = None
            backend._cat_cache["mtime"] = 0
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # ---------------- 已装插件一览
    def list_installed(self):
        try:
            return backend.list_installed()
        except Exception as e:
            traceback.print_exc()
            return {"ok": False, "error": str(e)}

    # ---------------- 主题持久化
    def load_theme(self):
        try:
            p = THEME_FILE
            if p.exists():
                return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
        return {}

    def save_theme(self, theme):
        try:
            THEME_FILE.parent.mkdir(parents=True, exist_ok=True)
            THEME_FILE.write_text(json.dumps(theme, ensure_ascii=False, indent=2), encoding="utf-8")
            return True
        except Exception:
            return False

    # ---------------- 内部
    def _emit(self, event, payload):
        if not self._win:
            return
        try:
            js = (
                f"window.__pmEmit && window.__pmEmit("
                f"{json.dumps(event)}, {json.dumps(payload, ensure_ascii=False)});"
            )
            self._win.evaluate_js(js)
        except Exception:
            pass


def _set_app_user_model_id():
    """Windows 任务栏把进程归组到某个 AppID 下。
    不设的话任务栏图标是 python 的、右键菜单里显示 python。"""
    if os.name != "nt":
        return
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "ShiZhen.PluginConsole.1"
        )
    except Exception:
        pass


def _force_window_icon(title_part="插件管家"):
    """pywebview 的 icon 参数只在 WinForms 后端生效、且时机偏早，
    某些情况下窗口图标还是 python 默认的那个。
    这里等窗口出现后，用 Win32 再强设一次（发送 WM_SETICON）。"""
    if os.name != "nt":
        return
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        icon_path = str(RES / "icon.ico")
        if not Path(icon_path).exists():
            return

        # 载入 ico 的大图标(32x32)和小图标(16x16)
        IMAGE_ICON = 1
        LR_LOADFROMFILE = 0x00000010
        LR_DEFAULTSIZE = 0x00000040
        WM_SETICON = 0x0080
        ICON_BIG, ICON_SMALL = 1, 0

        hicon_big = user32.LoadImageW(
            0, icon_path, IMAGE_ICON, 0, 0, LR_LOADFROMFILE | LR_DEFAULTSIZE
        )
        hicon_small = user32.LoadImageW(
            0, icon_path, IMAGE_ICON, 16, 16, LR_LOADFROMFILE
        )

        # 枚举顶层窗口，找标题匹配的
        found = []

        @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        def enum_proc(hwnd, lparam):
            try:
                length = user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buf = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(hwnd, buf, length + 1)
                    if title_part in buf.value:
                        found.append(hwnd)
            except Exception:
                pass
            return True

        user32.EnumWindows(enum_proc, 0)

        for hwnd in found:
            if hicon_big:
                user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, hicon_big)
            if hicon_small:
                user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, hicon_small)
    except Exception:
        pass


def main():
    _set_app_user_model_id()

    api = Api()
    html = RES / "ui" / "index.html"

    if not html.exists():
        print(f"找不到界面文件：{html}")
        return 1

    win = webview.create_window(
        "插件管家",
        url=str(html),
        js_api=api,
        width=1120,
        height=740,
        min_size=(900, 580),
        background_color="#0a0e17",
        frameless=False,
        easy_drag=False,
        text_select=True,
    )
    api.bind(win)

    # 窗口出来后再强设一次图标（延迟 0.8 秒，等窗口真正创建完）
    def _late_icon():
        import time
        time.sleep(0.8)
        _force_window_icon()

    threading.Thread(target=_late_icon, daemon=True).start()

    # icon 参数只给 Windows（WinForms 后端只认 .ico）
    kwargs = {"debug": False}
    icon_path = RES / "icon.ico"
    if os.name == "nt" and icon_path.exists():
        kwargs["icon"] = str(icon_path)

    try:
        webview.start(**kwargs)
    except TypeError:
        # 老版本 pywebview 不认 icon 参数
        kwargs.pop("icon", None)
        webview.start(**kwargs)

    return 0


if __name__ == "__main__":
    sys.exit(main())
