// Popup panel logic — matches Python/PySide6 version
// Uses window.__TAURI__ directly (withGlobalTauri), no import

import { resizeToFit } from './utils.js';

let compact = false;
let lastRightClickTime = 0;
let lastRightClickX = 0;
let lastRightClickY = 0;
let pendingUsage = null;  // 缓存后台数据，窗口可见时再渲染

// Safe access to Tauri APIs
function tauriInvoke(cmd, args) {
    return window.__TAURI__.core.invoke(cmd, args);
}
function tauriListen(event, handler) {
    return window.__TAURI__.event.listen(event, handler);
}

const app = document.getElementById('app');
const titleBar = document.querySelector('.title-bar');
const contentEl = document.querySelector('.content');
const footerEl = document.querySelector('.footer');
const refreshBtn = document.getElementById('refresh-btn');
const settingsBtn = document.getElementById('settings-btn');

// ─── Init ───
async function init() {
    try {
        const config = await tauriInvoke('get_config');
        compact = config.compact_mode || false;
    } catch (e) {
        console.error('get_config failed:', e);
    }

    if (compact) applyCompactMode();

    // Register event listeners BEFORE initial fetch to avoid missing events
    tauriListen('usage-updated', function(event) {
        // 窗口不可见时只缓存数据，不渲染 DOM。
        // 对隐藏的 WebView2 更新 DOM 会触发渲染，在 Windows 上
        // 导致临时窗口闪现（任务栏上两个空白窗口反复开关）。
        var win = window.__TAURI__.window.getCurrentWindow();
        win.isVisible().then(function(visible) {
            if (visible) {
                renderUsage(event.payload);
            } else {
                pendingUsage = event.payload;
            }
        }).catch(function() {
            renderUsage(event.payload);
        });
    });
    tauriListen('trigger-refresh', async function() {
        // trigger-refresh 在 popup 显示时触发（main.rs toggle_popup_window），
        // 此时窗口已可见。如果有缓存的后台数据先渲染，再拉取最新。
        if (pendingUsage) {
            renderUsage(pendingUsage);
            pendingUsage = null;
        }
        await refreshUsage();
    });

    await refreshUsage();
}

async function refreshUsage() {
    contentEl.innerHTML = '<div class="loading">刷新中...</div>';
    try {
        const usages = await tauriInvoke('fetch_all_usage');
        renderUsage(usages);
    } catch (e) {
        console.error('fetch_all_usage failed:', e);
        contentEl.innerHTML = '<div class="loading">加载失败</div>';
    }
}

// ─── Helpers ───
function pctColor(pct) {
    if (pct < 50) return '#4CAF50';
    if (pct < 80) return '#FFC107';
    return '#F44336';
}

function shortLabel(label) {
    return label
        .replace('Token 配额', 'Token').replace('Token限额', 'Token')
        .replace('MCP/时间配额', 'MCP').replace('MCP/时间限额', 'MCP')
        .replace('Session 用量', 'Session')
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
        return h + '时' + m + '分后重置';
    } catch { return ''; }
}

function esc(text) {
    var d = document.createElement('div');
    d.textContent = text;
    return d.innerHTML;
}

// ─── Render ───
function renderUsage(usages) {
    if (!usages || usages.length === 0) {
        contentEl.innerHTML = '<div class="loading">加载中...</div>';
        return;
    }

    var active = usages.filter(function(u) { return u.status !== 'no_api_key'; });

    if (active.length === 0) {
        contentEl.innerHTML =
            '<div class="setup-guide">' +
            '<p>请先在设置中配置您的 API 密钥</p>' +
            '<button class="guide-btn" id="guide-settings-btn">打开设置</button>' +
            '</div>';
        document.getElementById('guide-settings-btn').onclick = openSettings;
        doResize();
        return;
    }

    // Expanded HTML
    var exp = '';
    for (var i = 0; i < active.length; i++) {
        exp += renderExpandedCard(active[i]);
    }

    // Compact HTML — two-column layout matching Python UsagePopup._build_compact_page()
    var cmp = '';
    for (var j = 0; j < active.length; j++) {
        cmp += renderCompactRow(active[j]);
    }

    contentEl.dataset.expanded = exp;
    contentEl.dataset.compact = cmp;
    contentEl.innerHTML = compact ? cmp : exp;
    doResize();
}

// ─── Expanded Card (matches Python ProviderCard._build) ───
function renderExpandedCard(u) {
    var h = '<div class="provider-card">';

    // Header
    h += '<div class="card-header">';
    h += '<span class="provider-name">' + esc(u.provider_name) + '</span>';
    if (u.status !== 'ok') {
        var txt = u.status === 'error' ? '错误'
            : u.status === 'unauthorized' ? '未授权'
            : u.status === 'no_api_key' ? '未设置密钥' : '';
        h += '<span class="status-badge">' + txt + '</span>';
    }
    h += '</div>';

    if (u.plan_name) h += '<div class="plan-name">套餐: ' + esc(u.plan_name) + '</div>';
    if (u.error_message) h += '<div class="error-msg">' + esc(u.error_message) + '</div>';

    for (var i = 0; i < u.windows.length; i++) {
        var w = u.windows[i];
        var c = pctColor(w.used_percent);
        var reset = formatResetTime(w.resets_at);
        var detail = w.used_percent.toFixed(0) + '%';
        if (reset) detail += ' (' + reset + ')';

        h += '<div class="usage-window">';
        h += '<div class="usage-header">';
        h += '<span class="usage-label">' + esc(w.label) + '</span>';
        h += '<span class="usage-detail" style="color:' + c + '">' + detail + '</span>';
        h += '</div>';
        h += '<div class="progress-bar"><div class="progress-fill" style="width:' +
            Math.min(w.used_percent, 100) + '%;background:' + c + '"></div></div>';
        h += '</div>';
    }

    if (u.balance != null) h += '<div class="balance">余额: $' + u.balance.toFixed(2) + '</div>';
    if (u.plan_expires) h += '<div class="balance" style="color:#FFC107;">到期: ' + esc(u.plan_expires) + '</div>';

    var t = u.updated_at || '';
    h += '<div class="updated-at">更新: ' + esc(t) + '</div>';
    h += '</div>';
    return h;
}

// ─── Compact Row (matches Python UsagePopup._build_compact_page)
// Layout: [name box 65px] [quota rows with label + bar + pct]
function renderCompactRow(u) {
    var name = shortName(u.provider_name);

    var h = '<div class="compact-row">';
    // Left: name box
    h += '<div class="compact-name"><span>' + esc(name) + '</span></div>';
    // Right: quotas
    h += '<div class="compact-quotas">';

    if (u.windows.length === 0) {
        var errText = u.status === 'ok' ? '无数据' : u.status === 'error' ? '错误' : '未授权';
        var errColor = u.status === 'ok' ? '#888' : u.status === 'error' ? '#F44336' : '#FF9800';
        h += '<span class="compact-error" style="color:' + errColor + '">' + errText + '</span>';
    } else {
        for (var i = 0; i < u.windows.length; i++) {
            var w = u.windows[i];
            var c = pctColor(w.used_percent);
            var label = shortLabel(w.label);
            h += '<div class="quota-row">';
            h += '<span class="quota-label">' + esc(label) + '</span>';
            h += '<div class="quota-bar"><div class="progress-fill" style="width:' +
                Math.min(w.used_percent, 100) + '%;background:' + c + '"></div></div>';
            h += '<span class="quota-pct" style="color:' + c + '">' + w.used_percent.toFixed(0) + '%</span>';
            h += '</div>';
        }
    }

    if (u.balance != null) {
        h += '<span style="color:#4CAF50;font-size:11px">$' + u.balance.toFixed(2) + '</span>';
    }

    h += '</div></div>';
    return h;
}

// ─── Resize window to fit content ───
function doResize() {
    resizeToFit('app');
}

// ─── Toggle ───
function toggleCompact() {
    compact = !compact;
    applyCompactMode();
    contentEl.innerHTML = compact ? contentEl.dataset.compact : contentEl.dataset.expanded;
    doResize();
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
document.addEventListener('contextmenu', function(e) {
    e.preventDefault();
    var now = Date.now();
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
document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
        window.__TAURI__.window.getCurrentWindow().hide();
    }
});

// ─── Button handlers ───
refreshBtn.onclick = function() {
    refreshUsage();
};

settingsBtn.onclick = function() {
    openSettings();
};

// ─── Drag ───
titleBar.addEventListener('mousedown', function(e) {
    if (e.button === 0) {
        window.__TAURI__.window.getCurrentWindow().startDragging();
    }
});

app.addEventListener('mousedown', function(e) {
    if (compact && e.button === 0) {
        window.__TAURI__.window.getCurrentWindow().startDragging();
    }
});

function openSettings() {
    tauriInvoke('show_settings_window').catch(function(e) {
        console.error('openSettings error:', e);
    });
}

window.openSettings = openSettings;

// Start
init();
