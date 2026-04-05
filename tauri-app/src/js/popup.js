// Popup panel logic — matches Python/PySide6 version
const { invoke } = window.__TAURI__.core;
const { listen } = window.__TAURI__.event;

let compact = false;
let lastRightClickTime = 0;
let lastRightClickX = 0;
let lastRightClickY = 0;

const app = document.getElementById('app');
const titleBar = document.querySelector('.title-bar');
const contentEl = document.querySelector('.content');
const footerEl = document.querySelector('.footer');
const refreshBtn = document.getElementById('refresh-btn');
const settingsBtn = document.getElementById('settings-btn');

// Initialize
async function init() {
    try {
        const config = await invoke('get_config');
        compact = config.compact_mode || false;
    } catch (e) {
        console.error('Failed to get config:', e);
    }

    if (compact) applyCompactMode();
    await refreshUsage();

    listen('usage-updated', (event) => renderUsage(event.payload));
    listen('trigger-refresh', async () => { await refreshUsage(); });
}

async function refreshUsage() {
    try {
        const usages = await invoke('fetch_all_usage');
        renderUsage(usages);
    } catch (e) {
        console.error('Failed to fetch usage:', e);
        contentEl.innerHTML = '<div class="loading">加载失败</div>';
    }
}

function pctColor(pct) {
    if (pct < 50) return '#4CAF50';
    if (pct < 80) return '#FFC107';
    return '#F44336';
}

function shortLabel(label) {
    return label
        .replace('Token 配额', 'Token').replace('Token限额', 'Token')
        .replace('MCP/时间配额', 'MCP').replace('MCP/时间限额', 'MCP')
        .replace('5小时配额', '5小时').replace('5小时限额', '5小时')
        .replace('每周配额', '每周').replace('每周限额', '每周')
        .replace('每月配额', '每月').replace('每月限额', '每月')
        .replace('时间配额', '时间');
}

function shortName(name) {
    return name.split('(')[0].split('（')[0].trim();
}

function formatResetTime(resetsAt) {
    if (!resetsAt) return '';
    try {
        const d = new Date(resetsAt);
        const diff = d - Date.now();
        if (diff <= 0) return '';
        const h = Math.floor(diff / 3600000);
        const m = Math.floor((diff % 3600000) / 60000);
        return `${h}时${m}分后重置`;
    } catch { return ''; }
}

function esc(text) {
    const d = document.createElement('div');
    d.textContent = text;
    return d.innerHTML;
}

// ─── Render ───
function renderUsage(usages) {
    if (!usages || usages.length === 0) {
        contentEl.innerHTML = '<div class="loading">加载中...</div>';
        return;
    }

    const active = usages.filter(u => u.status !== 'no_api_key');

    if (active.length === 0) {
        contentEl.innerHTML = `
            <div class="setup-guide">
                <p>请先在设置中配置您的 API 密钥</p>
                <button class="guide-btn" id="guide-settings-btn">打开设置</button>
            </div>`;
        document.getElementById('guide-settings-btn').addEventListener('click', openSettings);
        resizeToFit();
        return;
    }

    // Expanded HTML
    let exp = '';
    for (const u of active) {
        exp += renderExpandedCard(u);
    }

    // Compact HTML (single-line per provider, like Python version)
    let cmp = '';
    for (const u of active) {
        cmp += renderCompactLine(u);
    }

    contentEl.dataset.expanded = exp;
    contentEl.dataset.compact = cmp;
    contentEl.innerHTML = compact ? cmp : exp;
    resizeToFit();
}

// Expanded card — matches Python ProviderCard._build()
function renderExpandedCard(u) {
    let h = '<div class="provider-card">';

    // Header
    h += '<div class="card-header">';
    h += `<span class="provider-name">${esc(u.provider_name)}</span>`;
    if (u.status !== 'ok') {
        const txt = u.status === 'error' ? '错误'
            : u.status === 'unauthorized' ? '未授权'
            : u.status === 'no_api_key' ? '未设置密钥' : '';
        h += `<span class="status-badge status-${u.status}">${txt}</span>`;
    }
    h += '</div>';

    // Plan
    if (u.plan_name) h += `<div class="plan-name">套餐: ${esc(u.plan_name)}</div>`;
    if (u.error_message) h += `<div class="error-msg">${esc(u.error_message)}</div>`;

    // Windows with progress bars
    for (const w of u.windows) {
        const c = pctColor(w.used_percent);
        const reset = formatResetTime(w.resets_at);
        const detail = [`${w.used_percent.toFixed(0)}%`];
        if (reset) detail.push(reset);

        h += '<div class="usage-window">';
        h += '<div class="usage-header">';
        h += `<span class="usage-label">${esc(w.label)}</span>`;
        h += `<span class="usage-detail" style="color:${c}">${detail.join('  ')}</span>`;
        h += '</div>';
        h += `<div class="progress-bar"><div class="progress-fill" style="width:${Math.min(w.used_percent, 100)}%;background:${c}"></div></div>`;
        h += '</div>';
    }

    if (u.balance != null) h += `<div class="balance">余额: $${u.balance.toFixed(2)}</div>`;

    const t = u.updated_at || new Date().toLocaleTimeString('zh-CN');
    h += `<div class="updated-at">更新: ${esc(t)}</div>`;
    h += '</div>';
    return h;
}

// Compact line — matches Python ProviderCard._build_compact()
// Single line: "智谱：Token 45% | 每周 32% $0.50"
function renderCompactLine(u) {
    const name = shortName(u.provider_name);
    const parts = [`<span style="color:#e0e0e0;font-weight:bold">${esc(name)}：</span>`];

    if (u.windows.length === 0) {
        if (u.status === 'error') parts.push('<span style="color:#F44336">错误</span>');
        else if (u.status === 'unauthorized') parts.push('<span style="color:#FF9800">未授权</span>');
        else parts.push('<span style="color:#888">无数据</span>');
    } else {
        for (let i = 0; i < u.windows.length; i++) {
            if (i > 0) parts.push('<span style="color:#555"> | </span>');
            const w = u.windows[i];
            const c = pctColor(w.used_percent);
            const label = shortLabel(w.label);
            parts.push(`<span style="color:${c};font-weight:bold">${label} ${w.used_percent.toFixed(0)}%</span>`);
        }
    }

    if (u.balance != null) {
        parts.push(`<span style="color:#4CAF50"> $${u.balance.toFixed(2)}</span>`);
    }

    return `<div class="compact-line">${parts.join('')}</div>`;
}

// ─── Resize ───
async function resizeToFit() {
    await new Promise(r => requestAnimationFrame(r));
    await new Promise(r => requestAnimationFrame(r));

    const rect = app.getBoundingClientRect();
    const width = compact ? 380 : 420;
    let height = Math.ceil(rect.height) + 4;
    height = Math.max(height, 60);
    height = Math.min(height, 800);

    try {
        const win = window.__TAURI__.window.getCurrentWindow();
        const mod = window.__TAURI__.dpi || window.__TAURI__.window;

        if (mod.LogicalSize) {
            await win.setSize(new mod.LogicalSize(width, height));
        } else {
            await win.setSize({ type: 'Logical', width, height });
        }

        const monitor = await win.primaryMonitor();
        if (monitor) {
            const sW = monitor.size.width / monitor.scaleFactor;
            const sH = monitor.size.height / monitor.scaleFactor;
            const x = Math.round(sW - width - 16);
            const y = Math.round(sH - height - 60);
            const pos = mod.LogicalPosition
                ? new mod.LogicalPosition(Math.max(x, 0), Math.max(y, 0))
                : { type: 'Logical', x: Math.max(x, 0), y: Math.max(y, 0) };
            await win.setPosition(pos);
        }
    } catch (e) {
        console.error('resize failed:', e);
    }
}

// ─── Toggle ───
function toggleCompact() {
    compact = !compact;
    applyCompactMode();
    const exp = contentEl.dataset.expanded;
    const cmp = contentEl.dataset.compact;
    contentEl.innerHTML = compact ? cmp : exp;
    resizeToFit();
}

function applyCompactMode() {
    if (compact) {
        document.body.classList.add('compact');
        titleBar.style.display = 'none';
        footerEl.style.display = 'none';
    } else {
        document.body.classList.remove('compact');
        titleBar.style.display = '';
        footerEl.style.display = '';
    }
}

// ─── Events ───

// Right-click double → toggle mode
document.addEventListener('contextmenu', (e) => {
    e.preventDefault();
    const now = Date.now();
    if (now - lastRightClickTime < 500
        && Math.abs(e.clientX - lastRightClickX) < 8
        && Math.abs(e.clientY - lastRightClickY) < 8) {
        toggleCompact();
        lastRightClickTime = 0;
        return;
    }
    lastRightClickTime = now;
    lastRightClickX = e.clientX;
    lastRightClickY = e.clientY;
});

// Escape → hide
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        window.__TAURI__.window.getCurrentWindow().hide();
    }
});

// ─── Buttons (expanded mode footer) ───
refreshBtn.addEventListener('click', () => {
    refreshUsage();
});

settingsBtn.addEventListener('click', () => {
    openSettings();
});

// ─── Drag ───
titleBar.addEventListener('mousedown', (e) => {
    if (e.button === 0) {
        window.__TAURI__.window.getCurrentWindow().startDragging();
    }
});

// In compact mode, the whole panel is draggable
app.addEventListener('mousedown', (e) => {
    if (compact && e.button === 0) {
        window.__TAURI__.window.getCurrentWindow().startDragging();
    }
});

async function openSettings() {
    try {
        const { WebviewWindow } = window.__TAURI__.webviewWindow;
        const w = WebviewWindow.getByLabel('settings');
        if (w) {
            await w.show();
            await w.setFocus();
        }
    } catch (e) {
        console.error('openSettings failed:', e);
    }
}

// Expose for inline handlers
window.openSettings = openSettings;

// Start
init();
