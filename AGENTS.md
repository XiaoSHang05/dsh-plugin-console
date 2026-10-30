# AGENTS.md — 插件管家（Plugin Console）

> ⚠️ 本目录**有 `.git`**，DSH 的指令链会在这里截断，
> 所以**上一级的 `D:\大鲸鱼的工作间\AGENTS.md` 不会自动注入**。
> 因此下面把那条最重要的规矩**复制一份**在这里。

---

## ⛔⛔ 动代码之前（必读，不许跳）

**只要用户的话里出现：做软件 · 写脚本 · 写代码 · 改代码 · 加功能 · 修 bug · 调试 · 重构 · 写测试 · 做界面**
→ 都属于「要动代码」，必须走三步：

```
① 读 D:\大鲸鱼的工作间\AI-ku\00_system\技能索引-写代码与写脚本必读.md
② 从索引里挑一个技能，读 C:\Users\15113\.dsh\skills\<技能名>\SKILL.md
③ 按它的步骤走，并在回复里明说用了哪个
```

⛔ 不许凭感觉直接写代码
⛔ 不许说「这个简单不用走流程」
⛔ 必须在回复里写「这次按 xxx 技能走」或「这次没用技能，因为……」

> 为什么：`~/.dsh/skills/` 里 12 个工程技能中有 **6 个被作者锁了**
> （`disable-model-invocation: true`）：`to-spec` `to-tickets` `implement`
> `triage` `retro` `wayfinder`。这 6 个**不会出现在技能列表里**，
> 只能靠读索引 + 手动读文件才能用。

---

## 🧱 本项目的特有约束（踩过的坑）

| 规矩 | 为什么 |
|---|---|
| **打包必须放纯英文路径**（如 `D:\PluginConsole-build`） | 中文路径下 `pythonnet` 的 DLL 加载失败，exe 一启动就退 |
| **PyInstaller 只用 onedir** | onefile 要解压到临时目录，本机报 `Could not create temporary directory` |
| `.cmd` 启动器**必须纯 ASCII** | cmd.exe 按 GBK 解析，中文会乱 |
| **icon.ico 要 7 个尺寸** | 单尺寸 Windows 显示成白纸 |
| **图标要用实心块，不要细线描边** | 32px 下细线糊成一团 |
| **UI 里禁止 `color-mix()`** | pywebview 的 WebView 不支持，会导致整个主题变白 |
| **更新完必须先 `S.busy = false` 再 `doScan()`** | 否则被 `doScan` 自身的守卫跳过，界面不刷新 |
| **DSH 运行中不能写 `node_modules`** | 会把活进程搞崩 |
| `pnpm add` **不写 `bundles`** | 装了在 DSH 里看不见，必须手动加 |
| `git push` 有 SSL 问题 | 用 `gh api` 走 Contents API 推送 |

---

## 📦 项目结构

```
插件管家/
├── app.py          启动 + pywebview 桥接 + API
├── backend.py      核心：扫描/更新/卸载/回滚/查包/装包
├── paths.py        配置读取 + 路径探测
├── ledger.py       台账同步（可选）
├── ui/             界面（index.html / app.js / style.css / dialog.js / dialog.css）
├── build-exe.py    打包脚本（必须用纯英文目录）
└── make_icon.py    图标生成（7 尺寸）
```

---

## 主人

【宴城】，叫他名字、用「你」。我们是伙伴，不是服务关系。
