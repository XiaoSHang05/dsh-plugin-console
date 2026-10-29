/* ===================================================================
   自定义对话框（替换原生 confirm / alert）
   用法：
     await pmConfirm({ title, message, items, note, okText, cancelText, danger })
     await pmAlert({ title, message, kind })
   =================================================================== */

(function () {
  const ICONS = {
    info: '<svg viewBox="0 0 16 16" fill="none"><circle cx="8" cy="8" r="6.2" stroke="currentColor" stroke-width="1.5"/><path d="M8 7v4M8 4.8v.1" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/></svg>',
    warn: '<svg viewBox="0 0 16 16" fill="none"><path d="M8 2.6 14 13H2L8 2.6Z" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round"/><path d="M8 6.4v3M8 11.2v.1" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>',
    bad: '<svg viewBox="0 0 16 16" fill="none"><circle cx="8" cy="8" r="6.2" stroke="currentColor" stroke-width="1.5"/><path d="M5.8 5.8l4.4 4.4M10.2 5.8l-4.4 4.4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>',
    upd: '<svg viewBox="0 0 16 16" fill="none"><path d="M8 12V4M4.5 7.5 8 4l3.5 3.5" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/><path d="M3 13.5h10" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/></svg>',
    trash: '<svg viewBox="0 0 16 16" fill="none"><path d="M3.5 4.5h9M6 4.5V3h4v1.5M5 4.5l.6 8.5h4.8l.6-8.5" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    back: '<svg viewBox="0 0 16 16" fill="none"><path d="M3 8a5 5 0 1 1 1.5 3.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/><path d="M3 4v4h4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    save: '<svg viewBox="0 0 16 16" fill="none"><path d="M3 3h7l3 3v7H3V3Z" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round"/><path d="M6 3v3h4V3" stroke="currentColor" stroke-width="1.3"/></svg>'
  };

  function esc(s) {
    return String(s).replace(/[&<>"']/g, c => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    }[c]));
  }

  let activeResolve = null;

  function close(result) {
    const mask = document.getElementById('pmDlgMask');
    if (mask) mask.hidden = true;
    const r = activeResolve;
    activeResolve = null;
    if (r) r(result);
  }

  function open(opts) {
    return new Promise((resolve) => {
      // 上一个还没关就先关掉
      if (activeResolve) close(false);
      activeResolve = resolve;

      const {
        title = '确认',
        message = '',
        items = null,       // [{ name, ver }]
        note = '',
        okText = '确定',
        cancelText = '取消',
        kind = 'info',      // info | warn | bad
        icon = 'info',      // 上面 ICONS 的 key
        danger = false,
        alertOnly = false
      } = opts || {};

      let mask = document.getElementById('pmDlgMask');
      if (!mask) {
        mask = document.createElement('div');
        mask.id = 'pmDlgMask';
        mask.className = 'dlg-mask';
        document.body.appendChild(mask);
      }

      const icoKey = icon || (kind === 'bad' ? 'bad' : kind === 'warn' ? 'warn' : 'info');
      const icoCls = kind === 'bad' ? 'bad' : kind === 'warn' ? 'warn' : '';

      let listHtml = '';
      if (items && items.length) {
        listHtml = `<div class="dlg-list">${items.map(it => {
          const name = typeof it === 'string' ? it : it.name;
          const ver = (typeof it === 'object' && it.ver) ? `<span class="ver">${esc(it.ver)}</span>` : '';
          return `<div class="dlg-list-item"><span>${esc(name)}</span>${ver}</div>`;
        }).join('')}</div>`;
      }

      const noteHtml = note
        ? `<div class="dlg-note"><svg viewBox="0 0 16 16" fill="none"><circle cx="8" cy="8" r="6.2" stroke="currentColor" stroke-width="1.5"/><path d="M8 7v4M8 4.8v.1" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/></svg><span>${esc(note)}</span></div>`
        : '';

      mask.innerHTML = `
        <div class="dlg" role="dialog" aria-modal="true">
          <div class="dlg-h">
            <div class="dlg-ico ${icoCls}">${ICONS[icoKey] || ICONS.info}</div>
            <div class="dlg-title">${esc(title)}</div>
          </div>
          <div class="dlg-b">
            ${message ? `<p class="dlg-msg">${esc(message)}</p>` : ''}
            ${listHtml}
            ${noteHtml}
          </div>
          <div class="dlg-f">
            ${alertOnly ? '' : `<button class="btn btn-ghost" data-act="cancel">${esc(cancelText)}</button>`}
            <button class="btn ${danger ? 'btn-danger' : 'btn-primary'}" data-act="ok">${esc(okText)}</button>
          </div>
        </div>`;

      mask.hidden = false;

      const okBtn = mask.querySelector('[data-act="ok"]');
      const cancelBtn = mask.querySelector('[data-act="cancel"]');
      if (okBtn) { okBtn.focus(); okBtn.onclick = () => close(true); }
      if (cancelBtn) cancelBtn.onclick = () => close(false);

      // 点遮罩空白处 = 取消
      mask.onclick = (e) => { if (e.target === mask) close(false); };

      // Esc = 取消，Enter = 确定
      mask.onkeydown = (e) => {
        if (e.key === 'Escape') { e.preventDefault(); close(false); }
        else if (e.key === 'Enter') { e.preventDefault(); close(true); }
      };
      mask.tabIndex = -1;
      mask.focus();
    });
  }

  // 对外：确认框
  window.pmConfirm = function (opts) {
    return open({ okText: '确定', cancelText: '取消', ...opts });
  };

  // 对外：提示框（只有一个按钮）
  window.pmAlert = function (opts) {
    const o = typeof opts === 'string' ? { message: opts } : (opts || {});
    return open({ title: '提示', okText: '知道了', alertOnly: true, ...o });
  };
})();
