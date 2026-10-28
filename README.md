# 插件管家 · Plugin Console

> 给 [DeepSeek Harness](https://github.com/deepseek-ai)（DSH）用的插件管理器。
> 检查更新、升级、卸载、回滚、分类查看，全都在这一个窗口里。

**为什么需要它**：DSH 的插件靠 pnpm 管理，命令行操作容易踩坑——「下载冷静期」会把新版本悄悄装成旧版、`pnpm add` 只写 `dependencies` 不写 `bundles`（装了看不见）、git 依赖会让整批安装回滚……这些坑一个脚本全填了。

---

## ✨ 功能

| 功能 | 说明 |
|---|---|
| **检查更新** | 逐个查云端最新版，标出「补丁级 / 功能级 / 大版本」 |
| **一键升级** | 自动备份 → 摘出 git 依赖 → 装 → 校验 → 挂 bundles |
| **卸载** | `dependencies` + `bundles` + `node_modules` 三处一起清 |
| **回滚** | 从历史备份恢复，当前状态自动另存 |
| **插件一览** | 按 10 个分类分组，带中文说明，可搜索可折叠 |
| **6 套主题** | 深空青 / 暗夜紫 / 终端绿 / 熔岩橙 / 极简墨 / 冰川蓝 |

### 踩过的坑，都修在代码里

- **pnpm「下载冷静期」**：新版本不在 `minimumReleaseAgeExclude` 白名单里，pnpm 会**悄悄装成旧版**，exit 0 还不报错 → 自动写入白名单
- **`pnpm add` 不写 `bundles`**：装完 `node_modules` 里有、DSH 里看不见 → 自动挂载
- **git 依赖拖垮整批**：`pnpm add` 解析整棵依赖树会去 `git fetch`，连不上就 `ERR_PNPM_GIT_FETCH_FAILED` 整批回滚 → 临时摘出，装完放回
- **DSH 运行中改 `node_modules`**：会把活进程搞崩 → 检测到运行中，所有写操作按钮直接变灰
- **备份无限膨胀**：→ 每类最多留 3 份

---

## 🚀 安装

### 需要

- Windows（用到了 `pythonw` 和系统 WebView）
- Python 3.10+
- `pip install pywebview`

### 用

```bat
git clone <this-repo>
cd plugin-console
copy config.example.json config.json
```

双击 **`启动插件管家.cmd`**。首次运行会自动探测你的 DSH profile 并写进 `config.json`。

---

## ⚙️ 配置

`config.json`（从 `config.example.json` 复制）。**所有项写 `null` 都会自动探测**：

| 项 | 说明 |
|---|---|
| `profile` | DSH profile 目录。`null` → 找 `~/.dsh/profiles/desktop` |
| `dshRoots` | DSH 安装目录。`null` → 探测常见位置 |
| `backupRoot` | 备份放哪。`null` → 程序目录下 `_backups` |
| `ledgerPath` | **台账路径。普通用户留 `null`**（见下） |
| `registry` | npm 源，默认 npmmirror |
| `keepBackups` | 每类备份保留份数，默认 3 |

### 关于 `ledgerPath`

这是一个**可选增强**：如果你有一个 Markdown 台账文件（形如 `| 插件 | 干什么的 | 版本 | 状态 |` 的表格），填上路径后，每次升级会自动把新版本号写回台账 + 追加更新记录。

**不需要就留 `null`**，其他功能完全不受影响，中文说明照样有（来自自带的 `descriptions.json`）。

---

## 📁 结构

```
plugin-console/
├── app.py              启动 + pywebview 桥接
├── backend.py          核心：扫描 / 更新 / 卸载 / 回滚
├── paths.py            配置读取 + 路径自动探测
├── ledger.py           台账同步（可选，ledgerPath=null 时不启用）
├── categories.json     10 个分类规则（改这个就能改分类）
├── descriptions.json   插件中文说明词典（37 条）
├── config.example.json 配置模板
├── ui/                 界面（HTML + CSS + JS）
├── icon.ico            图标
├── make_icon.py        图标生成脚本（纯 Python 画，无依赖）
└── 启动插件管家.cmd     双击启动
```

---

## 🔒 安全设计

1. **DSH 运行中绝不写盘** —— 按钮变灰，不是提示一下就放行
2. **每次写操作前备份** —— `package.json` / `pnpm-lock.yaml` / `pnpm-workspace.yaml`
3. **备份最多 3 份** —— 自动轮转
4. **回滚前另存当前状态** —— 回滚错了还能再回来
5. **校验 `bundles` 完整性** —— 更新前后对比，丢一条就醒目报错

---

## 📝 分类

分类规则在 `categories.json`，**改 JSON 就能改分类，不用动代码**：

```json
{
  "categories": [
    { "id": "memory", "name": "记忆与知识", "color": "#a78bfa",
      "keywords": { "记忆": 5, "memory": 5, "灵枢": 5 } }
  ],
  "overrides": { "某个包名": "某个分类 id" }
}
```

三层判定：`overrides` 手动指定 → 关键词**加权打分**取最高分 → 都不中归「其他」。

---

## 📄 License

MIT
