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

HERE = Path(__file__).parent
THEME_FILE = HERE / "theme.json"
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


def main():
    api = Api()
    html = HERE / "ui" / "index.html"

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

    webview.start(debug=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
