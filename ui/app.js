'use strict';
/* 插件管家 · 前端
   通过 window.pywebview.api 调后端；后端用 window.__pmEmit 推事件。 */

const $  = (s) => document.querySelector(s);
const $$ = (s) => [...document.querySelectorAll(s)];

const S = {
  rows: [],
  filter: 'all',
  selected: new Set(),
  busy: false,
  dshRunning: 0,
  dshVer: null,
  ready: false,
  tab: 'update',
  installed: [],
  groups: [],
  collapsed: new Set(),
  theme: 'abyss',
};

// ---------------------------------------------------------------- 主题
const THEMES = [
  { id: 'abyss',  name: '深空青',   desc: '默认 · 冷静科技感', bg: '#0a0e17', accent: '#22d3ee' },
  { id: 'violet', name: '暗夜紫',   desc: '柔和 · 偏文艺',     bg: '#0c0a14', accent: '#a78bfa' },
  { id: 'matrix', name: '终端绿',   desc: '极客 · 复古终端',   bg: '#050807', accent: '#4ade80' },
  { id: 'ember',  name: '熔岩橙',   desc: '温暖 · 高强度',     bg: '#100b08', accent: '#fb923c' },
  { id: 'ink',    name: '极简墨',   desc: '浅色 · 干净白纸',   bg: '#f7f8fa', accent: '#0f766e' },
  { id: 'frost',  name: '冰川蓝',   desc: '浅色 · 冷调清透',   bg: '#eef2f8', accent: '#2563eb' },
];

function applyTheme(id) {
  const t = THEMES.find(x => x.id === id) ? id : 'abyss';
  document.documentElement.setAttribute('data-theme', t);
  S.theme = t;
  renderThemeGrid();
}

function renderThemeGrid() {
  const g = $('#themeGrid');
  if (!g) return;
  g.innerHTML = THEMES.map(t => {
    const active = t.id === S.theme;
    return `
      <div class="theme-card ${active ? 'active' : ''}" data-theme-id="${t.id}">
        <div class="theme-swatch" style="background:${t.bg};color:${t.accent}">
          <div class="theme-cur"><svg viewBox="0 0 10 10" fill="none"><path d="M2 5.2l2.2 2.2L8 3" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg></div>
        </div>
        <div class="theme-name">${esc(t.name)}</div>
        <div class="theme-desc">${esc(t.desc)}</div>
      </div>`;
  }).join('');

  g.querySelectorAll('.theme-card').forEach(el => {
    el.onclick = async () => {
      const id = el.dataset.themeId;
      applyTheme(id);
      try {
        const api = window.pywebview && window.pywebview.api;
        if (api && api.save_theme) await api.save_theme({ theme: id });
      } catch { /* 存不住也不影响用 */ }
    };
  });
}

// ---------------------------------------------------------------- 工具
const esc = (s) => String(s == null ? '' : s)
  .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
  .replace(/"/g, '&quot;').replace(/'/g, '&#39;');

const api = () => window.pywebview && window.pywebview.api;

window.__pmEmit = (event, payload) => {
  if (event === 'scan:progress') {
    const { done, total, name } = payload;
    progress(true, (done / Math.max(1, total)) * 100, `查询 ${done}/${total}　${name}`);
  } else if (event === 'act:log') {
    log(payload);
  } else if (event === 'act:progress') {
    const { i, total, name } = payload;
    progress(true, (i / Math.max(1, total)) * 100, `安装 ${i}/${total}　${name}`);
  }
};

// ---------------------------------------------------------------- 状态
function setStatusChip(running, ver) {
  const el = $('#dshStatus');
  if (!el) return;
  const txt = el.querySelector('.txt');
  el.classList.remove('on', 'off');
  if (running > 0) {
    el.classList.add('on');
    txt.textContent = `DSH 运行中 · ${running} 进程`;
  } else {
    el.classList.add('off');
    txt.textContent = ver ? `DSH 已关闭 · ${ver}` : 'DSH 已关闭';
  }
  S.dshRunning = running;
  S.dshVer = ver;
  syncButtons();
}

function syncButtons() {
  const ids = ['#btnScan', '#btnUpdate', '#btnUninstall', '#btnRollback'];
  if (!S.ready) { ids.forEach(s => { const e = $(s); if (e) e.disabled = true; }); return; }

  const canWrite = S.dshRunning === 0 && !S.busy;
  const upd = S.rows.filter(r => r.verdict === 'UPDATE');
  const selUpd = [...S.selected].filter(n => upd.some(r => r.name === n));

  $('#btnScan').disabled = S.busy;
  $('#btnUpdate').disabled = !canWrite || selUpd.length === 0;
  $('#btnUninstall').disabled = !canWrite || S.selected.size === 0;
  $('#btnRollback').disabled = !canWrite;

  const badge = $('#selCount');
  if (selUpd.length > 0) { badge.hidden = false; badge.textContent = String(selUpd.length); }
  else badge.hidden = true;
}

function log(text) {
  const box = $('#logBox');
  if (!box) return;
  const line = String(text == null ? '' : text).replace(/\r/g, '');
  box.textContent += line + (line.endsWith('\n') ? '' : '\n');
  box.scrollTop = box.scrollHeight;
  if (!$('#logDrawer').classList.contains('open')) $('#logDot').hidden = false;
}

function clearLog() { const b = $('#logBox'); if (b) b.textContent = ''; $('#logDot').hidden = true; }

function progress(show, pct, text) {
  const wrap = $('#progWrap');
  if (!wrap) return;
  if (!show) { wrap.hidden = true; $('#progFill').style.width = '0%'; return; }
  wrap.hidden = false;
  $('#progFill').style.width = Math.max(0, Math.min(100, pct || 0)) + '%';
  $('#progText').textContent = text || '';
}

function showHint(text) {
  let el = $('#hintBar');
  if (!el) {
    el = document.createElement('div');
    el.id = 'hintBar';
    el.className = 'hint-bar';
    el.innerHTML = `<svg viewBox="0 0 16 16" fill="none"><path d="M8 5.5v4M8 11.4v.1" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/><circle cx="8" cy="8" r="6.2" stroke="currentColor" stroke-width="1.3"/></svg><span></span>`;
    const tb = $('.toolbar');
    if (tb) tb.after(el);
  }
  el.querySelector('span').textContent = text;
  el.hidden = false;
}
function hideHint() { const el = $('#hintBar'); if (el) el.hidden = true; }

// ---------------------------------------------------------------- 更新页渲染
const KIND_CLASS = { major: 'tag-major', minor: 'tag-minor', patch: 'tag-patch', local: 'tag-local', err: 'tag-err', ok: 'tag-ok' };

function rowTags(r) {
  const t = [];
  if (r.verdict === 'UPDATE' && r.jumpLabel) {
    t.push(`<span class="tag ${KIND_CLASS[r.kind] || 'tag-patch'}">${esc(r.jumpLabel)}</span>`);
  }
  if (r.verdict === 'SKIP') t.push('<span class="tag tag-skip">不兼容</span>');
  if (r.verdict === 'LOCAL') t.push('<span class="tag tag-local">本地</span>');
  if (r.verdict === 'ERR') t.push('<span class="tag tag-err">查询失败</span>');
  if (r.verdict === 'OK') t.push('<span class="tag tag-ok">已最新</span>');
  if (r.verdict !== 'LOCAL' && r.verdict !== 'ERR' && !r.mounted) {
    t.push('<span class="tag tag-nomount">未挂载</span>');
  }
  return t.join('');
}

function rowVer(r) {
  if (r.verdict === 'LOCAL' || r.verdict === 'ERR') return `<span class="ver-none">${esc(r.cur || '—')}</span>`;
  if (r.verdict === 'OK') return `<span class="ver-same">${esc(r.cur || '—')}</span>`;
  return `<span class="ver-cur">${esc(r.cur || '—')}</span>
          <span class="ver-arrow">→</span>
          <span class="ver-new">${esc(r.latest || '—')}</span>`;
}

function rowDesc(r) {
  const d = r.desc || '（无说明）';
  let note = '';
  if (r.verdict === 'UPDATE' && r.jumpHint) {
    note = `<div class="desc-note">${esc(r.jumpHint)}${r.note ? ' · ' + esc(r.note) : ''}</div>`;
  } else if (r.verdict === 'SKIP') {
    note = `<div class="desc-note warn">${esc(r.note || '')}</div>`;
  } else if (r.verdict === 'ERR') {
    note = `<div class="desc-note bad">${esc(r.note || '')}</div>`;
  } else if (r.verdict === 'LOCAL') {
    note = `<div class="desc-note">${esc(r.note || '')}</div>`;
  } else if (r.verdict !== 'ERR' && !r.mounted) {
    note = `<div class="desc-note warn">装了但没挂 bundles —— 在 DSH 里不会加载</div>`;
  }
  return `<div class="desc-main">${esc(d)}</div>${note}`;
}

function visibleRows() {
  if (S.filter === 'all') return S.rows;
  if (S.filter === 'update') return S.rows.filter(r => r.verdict === 'UPDATE');
  if (S.filter === 'ok') return S.rows.filter(r => r.verdict === 'OK');
  if (S.filter === 'local') return S.rows.filter(r => ['LOCAL', 'ERR', 'SKIP'].includes(r.verdict));
  return S.rows;
}

function render() {
  const body = $('#listBody');
  const list = visibleRows();

  if (!S.rows.length) {
    body.innerHTML = `
      <div class="empty">
        <div class="empty-ico">
          <svg viewBox="0 0 48 48" fill="none">
            <path d="M24 6L6 15v18l18 9 18-9V15L24 6z" stroke="currentColor" stroke-width="1.6"/>
            <path d="M24 16l-9 4.5v9L24 34l9-4.5v-9L24 16z" stroke="currentColor" stroke-width="1.2" opacity=".4"/>
          </svg>
        </div>
        <div class="empty-t">点「检查更新」开始</div>
        <div class="empty-s">会逐个向你已装的插件查询云端最新版</div>
      </div>`;
    updateStats();
    return;
  }

  if (!list.length) {
    body.innerHTML = `<div class="empty"><div class="empty-t">这个分类下没有插件</div></div>`;
    updateStats();
    return;
  }

  body.innerHTML = list.map(r => {
    const canSel = r.verdict !== 'ERR';
    const sel = S.selected.has(r.name);
    const cls = ['row',
      r.verdict === 'UPDATE' ? 'is-update' : '',
      r.verdict === 'SKIP' ? 'is-skip' : '',
      r.verdict === 'ERR' ? 'is-err' : '',
      sel ? 'is-sel' : ''].filter(Boolean).join(' ');
    return `
      <div class="${cls}">
        <label class="cb-wrap">
          <input type="checkbox" data-cb="${esc(r.name)}" ${sel ? 'checked' : ''} ${canSel ? '' : 'disabled'}>
          <span class="cb"></span>
        </label>
        <div class="col-name">
          <div class="pkg-name" title="${esc(r.name)}">${esc(r.name)}</div>
          <div class="pkg-tags">${rowTags(r)}</div>
        </div>
        <div class="col-ver"><div class="ver-flow">${rowVer(r)}</div></div>
        <div class="col-desc">${rowDesc(r)}</div>
      </div>`;
  }).join('');

  body.querySelectorAll('input[data-cb]').forEach(cb => {
    cb.addEventListener('change', () => {
      const n = cb.dataset.cb;
      if (cb.checked) S.selected.add(n); else S.selected.delete(n);
      cb.closest('.row')?.classList.toggle('is-sel', cb.checked);
      syncButtons();
      syncSelectAll();
    });
  });

  syncSelectAll();
  updateStats();
}

function updateStats() {
  const upd = S.rows.filter(r => r.verdict === 'UPDATE').length;
  const ok = S.rows.filter(r => r.verdict === 'OK').length;
  const loc = S.rows.filter(r => r.verdict === 'LOCAL').length;
  const err = S.rows.filter(r => r.verdict === 'ERR').length;
  const skip = S.rows.filter(r => r.verdict === 'SKIP').length;
  const parts = [`共 ${S.rows.length} 个插件`];
  if (upd) parts.push(`可更新 ${upd}`);
  if (ok) parts.push(`已最新 ${ok}`);
  if (skip) parts.push(`不兼容 ${skip}`);
  if (loc) parts.push(`本地 ${loc}`);
  if (err) parts.push(`查询失败 ${err}`);
  $('#footerStats').textContent = S.rows.length ? parts.join('  ·  ') : '—';

  const cu = $('#cntUpdate');
  if (cu) cu.textContent = S.rows.length ? (upd > 0 ? `${upd} 个可更新` : '无更新') : '—';
}

function syncSelectAll() {
  const cb = $('#cbAll');
  if (!cb) return;
  const list = visibleRows().filter(r => r.verdict !== 'ERR');
  const selIn = list.filter(r => S.selected.has(r.name));
  cb.checked = list.length > 0 && selIn.length === list.length;
  cb.indeterminate = selIn.length > 0 && selIn.length < list.length;
  cb.disabled = list.length === 0;
}

// ---------------------------------------------------------------- 插件一览
async function loadInstalled() {
  if (!api()) return;
  const body = $('#instBody');
  body.innerHTML = Array.from({ length: 6 }, () =>
    `<div class="skel">
       <div></div>
       <div class="skel-bar" style="width:62%"></div>
       <div class="skel-bar" style="width:78%"></div>
       <div class="skel-bar" style="width:88%"></div>
     </div>`).join('');

  try {
    const fn = api().list_installed_grouped || api().list_installed;
    const r = await fn();
    if (!r || !r.ok) {
      body.innerHTML = `<div class="inst-empty">读取失败：${esc((r && r.error) || '未知错误')}</div>`;
      return;
    }
    S.installed = r.rows || [];
    S.groups = r.groups || [];
    renderGrouped();
    const c = $('#cntAll');
    if (c) c.textContent = `${r.total} 个`;
  } catch (e) {
    body.innerHTML = `<div class="inst-empty">读取异常：${esc(e.message)}</div>`;
  }
}

/** 分类折叠状态：默认全展开 */
S.collapsed = new Set();

function renderGrouped() {
  const body = $('#instBody');
  const q = ($('#instSearch').value || '').trim().toLowerCase();

  let groups = S.groups || [];

  // 搜索时，只留命中的条目；组内空了就不显示这组
  if (q) {
    groups = groups.map(g => ({
      ...g,
      items: g.items.filter(x =>
        x.name.toLowerCase().includes(q) ||
        (x.desc || '').toLowerCase().includes(q) ||
        (x.catName || '').toLowerCase().includes(q)),
    })).filter(g => g.items.length > 0);
  }

  const total = (S.installed || []).length;
  const mounted = (S.installed || []).filter(x => x.mounted).length;
  const cnt = $('#instCount');
  if (cnt) {
    cnt.textContent = q
      ? `筛出 ${groups.reduce((a, g) => a + g.items.length, 0)} / ${total}`
      : `${total} 个插件 · ${mounted} 个已挂载 · ${(S.groups || []).length} 个分类`;
  }

  if (!groups.length) {
    body.innerHTML = `<div class="inst-empty">没找到匹配的插件</div>`;
    return;
  }

  body.innerHTML = groups.map(g => {
    const open = !S.collapsed.has(g.id);
    return `
      <div class="cat-group ${open ? '' : 'collapsed'}" data-cat="${esc(g.id)}">
        <div class="cat-head" data-toggle="${esc(g.id)}">
          <svg class="cat-chev" viewBox="0 0 16 16"><path d="M5 3l5 5-5 5" stroke="currentColor" stroke-width="1.7" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>
          <span class="cat-dot" style="background:${esc(g.color)};box-shadow:0 0 8px ${esc(g.color)}"></span>
          <span class="cat-name">${esc(g.name)}</span>
          <span class="cat-cnt">${g.count}</span>
          <span class="cat-desc">${esc(g.desc || '')}</span>
        </div>
        <div class="cat-body" style="${open ? '' : 'display:none'}">
          ${g.items.map(x => instRow(x)).join('')}
        </div>
      </div>`;
  }).join('');

  // 折叠
  body.querySelectorAll('[data-toggle]').forEach(el => {
    el.onclick = () => {
      const id = el.dataset.toggle;
      if (S.collapsed.has(id)) S.collapsed.delete(id);
      else S.collapsed.add(id);
      renderGrouped();
    };
  });
}

function instRow(x) {
  const unmounted = !x.mounted;
  const tags = [];
  if (x.isLocal) tags.push('<span class="tag tag-local">本地</span>');
  if (unmounted) tags.push('<span class="tag tag-nomount">未挂载</span>');
  if (!x.fromLedger && x.desc) tags.push('<span class="tag tag-local">英文说明</span>');
  return `
    <div class="inst-row ${unmounted ? 'unmounted' : ''}">
      <div class="inst-dot" style="${x.catColor ? 'background:' + esc(x.catColor) + ';box-shadow:0 0 7px ' + esc(x.catColor) : ''}"></div>
      <div>
        <div class="inst-name">
          <span>${esc(x.name)}</span>
          <span class="inst-ver">${esc(x.version || '—')}</span>
          ${tags.join('')}
        </div>
        <div class="inst-desc">${esc(x.desc || '（这个包没写说明）')}</div>
      </div>
    </div>`;
}

/** 兼容旧入口 */
function renderInstalled() { renderGrouped(); }

// ---------------------------------------------------------------- 动作
async function doScan() {
  if (S.busy || !api()) return;
  S.busy = true; S.selected.clear(); S.rows = [];
  syncButtons();
  progress(true, 0, '准备查询…');
  $('#listBody').innerHTML = Array.from({ length: 8 }, () =>
    `<div class="skel">
       <div></div>
       <div class="skel-bar" style="width:70%"></div>
       <div class="skel-bar" style="width:60%"></div>
       <div class="skel-bar" style="width:88%"></div>
     </div>`).join('');

  try {
    const r = await api().scan();
    if (!r || !r.ok) {
      log('扫描失败：' + ((r && r.error) || '未知错误'));
      progress(false); S.rows = []; render(); return;
    }
    S.rows = r.rows || [];
    setStatusChip(r.dshRunning || 0, r.dshVer || null);
    progress(false);
    render();
    const upd = S.rows.filter(x => x.verdict === 'UPDATE').length;
    log(`扫描完成：共 ${S.rows.length} 个，可更新 ${upd} 个`);
    if ((r.dshRunning || 0) > 0 && upd > 0) {
      showHint(`DSH 正在运行（${r.dshRunning} 个进程），现在不能写入。要更新请先彻底退出 DSH（托盘右键 → 退出），再点「检查更新」。`);
    } else hideHint();
  } catch (e) {
    log('扫描异常：' + e.message);
    progress(false); render();
  } finally {
    S.busy = false; syncButtons();
  }
}

async function doUpdate() {
  const upd = S.rows.filter(r => r.verdict === 'UPDATE').map(r => r.name);
  const names = [...S.selected].filter(n => upd.includes(n));
  if (!names.length || !api()) return;
  if (!confirm(`要升级这 ${names.length} 个插件吗？\n\n${names.join('\n')}\n\n升级前会自动备份。`)) return;

  S.busy = true; syncButtons(); openLog(); clearLog();
  log(`开始升级 ${names.length} 个插件…`);
  progress(true, 0, '准备…');

  try {
    const r = await api().update(names);
    progress(false);
    if (!r || r.error) { log('✗ ' + ((r && r.error) || '未知错误')); return; }

    log('');
    log('──────── 结果 ────────');
    for (const x of r.results || []) {
      log(`${x.ok ? '✓' : '✗'} ${x.name}　${x.from || '?'} → ${x.to || '读不到'}`);
    }
    if (r.mounted && r.mounted.length) log(`已挂进 bundles：${r.mounted.join(', ')}`);

    if (r.notes && r.notes.length) {
      log('');
      log('──────── 这次更新了什么 ────────');
      for (const n of r.notes) {
        log(`${n.name}　${n.from} → ${n.to}`);
        if (n.jump) log(`  【${n.jump.label}】${n.jump.hint}`);
        if (n.changelog && n.changelog.length) {
          for (const b of n.changelog) log(`  · ${b}`);
        } else {
          log('  · 具体改了什么：这个包没带 CHANGELOG，查不到');
        }
      }
    }
    log('');
    log(r.ok ? '✓ 全部成功。重新打开 DSH 生效。' : '有些没到位，看上面标 ✗ 的。');
    S.selected.clear();
    await doScan();
    await loadInstalled();
  } catch (e) {
    log('升级异常：' + e.message); progress(false);
  } finally {
    S.busy = false; syncButtons();
  }
}

async function doUninstall() {
  const names = [...S.selected];
  if (!names.length || !api()) return;
  if (!confirm(`要卸载这 ${names.length} 个插件吗？\n\n${names.join('\n')}\n\n会同时从 dependencies 和 bundles 里移除。`)) return;

  S.busy = true; syncButtons(); openLog(); clearLog();
  log(`开始卸载 ${names.length} 个插件…`);
  progress(true, 50, '正在移除…');

  try {
    const r = await api().uninstall(names);
    progress(false);
    if (!r || r.error) { log('✗ ' + ((r && r.error) || '未知错误')); return; }

    log('');
    log('──────── 检验 ────────');
    for (const v of r.verify || []) {
      const clean = !v.inDeps && !v.inBundles && !v.inNM;
      log(`${clean ? '✓' : '✗'} ${v.name}　deps=${v.inDeps ? 'Y' : 'N'} bundles=${v.inBundles ? 'Y' : 'N'} node_modules=${v.inNM ? 'Y' : 'N'}`);
    }
    log('');
    log(r.ok ? '✓ 卸载干净。重新打开 DSH 生效。' : '有残留，看上面标 ✗ 的。');
    S.selected.clear();
    await doScan();
    await loadInstalled();
  } catch (e) {
    log('卸载异常：' + e.message); progress(false);
  } finally {
    S.busy = false; syncButtons();
  }
}

async function openRollback() {
  if (!api()) return;
  const list = await api().list_backups();
  const body = $('#modalBody');
  if (!list || !list.length) {
    body.innerHTML = `<div class="bk-empty">还没有任何备份。<br>升级之前会自动生成。</div>`;
  } else {
    body.innerHTML = list.map(b =>
      `<div class="bk-item" data-id="${esc(b.id)}">
         <span class="bk-at">${esc(b.at)}</span>
         <span class="bk-go">回滚到这一版 →</span>
       </div>`).join('');
    body.querySelectorAll('.bk-item').forEach(el => {
      el.addEventListener('click', async () => {
        const id = el.dataset.id;
        if (!confirm(`要回滚到 ${id} 这一版吗？\n\n当前状态会先另存一份，回滚错了还能再回来。\n\n会重装依赖，需要一两分钟。`)) return;
        $('#modalMask').hidden = true;
        S.busy = true; syncButtons(); openLog(); clearLog();
        progress(true, 40, '正在恢复并重装…');
        try {
          const r = await api().rollback(id);
          progress(false);
          log(r && r.ok ? '✓ 回滚完成。重新打开 DSH 生效。' : `✗ 回滚失败：${(r && r.error) || ('exit ' + (r && r.code))}`);
          await doScan();
          await loadInstalled();
        } catch (e) { log('回滚异常：' + e.message); progress(false); }
        finally { S.busy = false; syncButtons(); }
      });
    });
  }
  $('#modalMask').hidden = false;
}

function openLog() {
  $('#logDrawer').classList.add('open');
  $('#logToggle').classList.add('open');
  $('#logDot').hidden = true;
}

// ---------------------------------------------------------------- 标签页切换
function switchTab(name) {
  S.tab = name;
  $$('.tab').forEach(t => t.classList.toggle('active', t.dataset.tab === name));
  $('#pageUpdate').style.display = name === 'update' ? 'flex' : 'none';
  $('#pageList').style.display = name === 'list' ? 'flex' : 'none';
  if (name === 'list' && !S.installed.length) loadInstalled();
}

// ---------------------------------------------------------------- 绑定
function bind() {
  $('#btnScan').onclick = doScan;
  $('#btnUpdate').onclick = doUpdate;
  $('#btnUninstall').onclick = doUninstall;
  $('#btnRollback').onclick = openRollback;

  $('#btnTheme').onclick = () => { renderThemeGrid(); $('#themeMask').hidden = false; };
  $('#themeClose').onclick = () => { $('#themeMask').hidden = true; };
  $('#themeMask').onclick = (e) => { if (e.target.id === 'themeMask') $('#themeMask').hidden = true; };

  $$('.tab').forEach(t => { t.onclick = () => switchTab(t.dataset.tab); });

  $('#instSearch').oninput = renderInstalled;

  $('#logToggle').onclick = () => {
    const open = $('#logDrawer').classList.toggle('open');
    $('#logToggle').classList.toggle('open', open);
    if (open) $('#logDot').hidden = true;
  };

  $('#cbAll').onchange = (e) => {
    const list = visibleRows().filter(r => r.verdict !== 'ERR');
    if (e.target.checked) list.forEach(r => S.selected.add(r.name));
    else list.forEach(r => S.selected.delete(r.name));
    render();
  };

  $$('#filterGroup .fg').forEach(b => {
    b.onclick = () => {
      $$('#filterGroup .fg').forEach(x => x.classList.remove('active'));
      b.classList.add('active');
      S.filter = b.dataset.f;
      render();
    };
  });

  $('#modalClose').onclick = () => { $('#modalMask').hidden = true; };
  $('#modalMask').onclick = (e) => { if (e.target.id === 'modalMask') $('#modalMask').hidden = true; };

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      $('#modalMask').hidden = true;
      $('#themeMask').hidden = true;
    }
  });
}

// ---------------------------------------------------------------- 启动
async function boot() {
  bind();

  const waitApi = () => new Promise((resolve) => {
    if (api()) return resolve();
    let n = 0;
    const t = setInterval(() => {
      n++;
      if (api() || n > 100) { clearInterval(t); resolve(); }
    }, 60);
  });
  await waitApi();

  if (!api()) {
    log('后端没有连接上。请用 启动插件管家.cmd 打开，不要直接双击 html。');
    $('#footerStats').textContent = '后端未连接';
    return;
  }

  S.ready = true;

  // 读主题
  try {
    const th = await api().load_theme();
    applyTheme((th && th.theme) || 'abyss');
  } catch { applyTheme('abyss'); }

  try {
    const env = await api().env_info();
    setStatusChip(env.running || 0, env.dshVer || null);
    if (!env.root) {
      log('找不到 DSH 安装目录');
      showHint('找不到 DSH 安装目录，插件操作可能不可用。');
    } else {
      log(`DSH ${env.dshVer || '版本未识别'}　·　${env.root}`);
      log(`Python ${env.python}　·　Profile ${env.profile}`);
    }
  } catch (e) {
    log('读取环境失败：' + e.message);
  }

  syncButtons();

  setInterval(async () => {
    if (!api() || S.busy) return;
    try {
      const p = await api().pulse();
      if ((p.running || 0) !== S.dshRunning) {
        setStatusChip(p.running || 0, p.ver || null);
        const hasUpd = S.rows.some(r => r.verdict === 'UPDATE');
        if ((p.running || 0) > 0 && hasUpd) {
          showHint(`DSH 正在运行（${p.running} 个进程），现在不能写入。要更新请先彻底退出 DSH。`);
        } else if ((p.running || 0) === 0) {
          hideHint();
        }
      }
    } catch { /* 忽略 */ }
  }, 2000);
}

window.addEventListener('DOMContentLoaded', boot);
