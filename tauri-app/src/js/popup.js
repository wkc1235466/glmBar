// Popup panel logic
import { fetchAllUsage, getConfig, listen } from './api.js';

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
    const config = await getConfig();
    compact = config.compact_mode || false;
    if (compact) applyCompactMode();

    // Initial fetch
    await refreshUsage();

    // Listen for usage updates from backend timer
    listen('usage-updated', (event) => {
        renderUsage(event.payload);
    });

    // Listen for manual refresh trigger
    listen('trigger-refresh', async () => {
        await refreshUsage();
    });
}

async function refreshUsage() {
    try {
        const usages = await fetchAllUsage();
        renderUsage(usages);
    } catch (e) {
        console.error('Failed to fetch usage:', e);
    }
}

function pctColor(pct) {
    if (pct < 50) return 'green';
    if (pct < 80) return 'yellow';
    return 'red';
}

function shortLabel(label) {
    if (label.includes('Token')) return 'Token';
    if (label.includes('5小时') || label.toLowerCase().includes('5hour')) return '5小时';
    if (label.includes('每周') || label.toLowerCase().includes('week')) return '每周';
    if (label.includes('每月') || label.toLowerCase().includes('month')) return '每月';
    if (label.includes('MCP') || label.includes('时间')) return 'MCP';
    return label;
}

function shortName(name) {
    return name.split('(')[0].split('（')[0].trim();
}

function formatResetTime(resetsAt) {
    if (!resetsAt) return '';
    try {
        const resetDate = new Date(resetsAt);
        const now = new Date();
        const diffMs = resetDate - now;
        if (diffMs <= 0) return '';
        const hours = Math.floor(diffMs / 3600000);
        const mins = Math.floor((diffMs % 3600000) / 60000);
        return `${hours}时${mins}分后重置`;
    } catch {
        return '';
    }
}

function renderUsage(usages) {
    if (!usages || usages.length === 0) {
        contentEl.innerHTML = '<div class="loading">加载中...</div>';
        return;
    }

    const activeUsages = usages.filter(u => u.status !== 'no_api_key');

    // Render expanded view
    let expandedHtml = '';
    if (activeUsages.length === 0) {
        expandedHtml = `
            <div class="setup-guide">
                <p>请先在设置中配置您的 API 密钥</p>
                <button onclick="openSettings()">打开设置</button>
            </div>
        `;
    } else {
        for (const usage of activeUsages) {
            expandedHtml += renderProviderCard(usage);
        }
    }

    // Render compact view
    let compactHtml = '';
    for (const usage of activeUsages) {
        compactHtml += renderCompactRow(usage);
    }

    // Store both views and render current
    contentEl.dataset.expanded = expandedHtml;
    contentEl.dataset.compact = compactHtml;
    contentEl.innerHTML = compact ? compactHtml : expandedHtml;

    // Resize window to fit content
    resizeToFit();
}

function renderProviderCard(usage) {
    let html = `<div class="provider-card">`;

    // Header
    html += `<div class="card-header">`;
    html += `<span class="provider-name">${escapeHtml(usage.provider_name)}</span>`;

    if (usage.status !== 'ok') {
        const statusText = usage.status === 'error' ? '错误'
            : usage.status === 'unauthorized' ? '未授权'
            : usage.status === 'no_api_key' ? '未设置密钥' : '';
        const statusClass = usage.status === 'error' ? 'status-error'
            : usage.status === 'unauthorized' ? 'status-unauthorized'
            : 'status-no-key';
        html += `<span class="status-badge ${statusClass}">${statusText}</span>`;
    }
    html += `</div>`;

    // Plan name
    if (usage.plan_name) {
        html += `<div class="plan-name">套餐: ${escapeHtml(usage.plan_name)}</div>`;
    }

    // Error message
    if (usage.error_message) {
        html += `<div class="error-msg">${escapeHtml(usage.error_message)}</div>`;
    }

    // Windows
    for (const w of usage.windows) {
        const color = pctColor(w.used_percent);
        const resetText = formatResetTime(w.resets_at);
        const detailParts = [`${w.used_percent.toFixed(0)}%`];
        if (resetText) detailParts.push(resetText);

        html += `<div class="usage-window">`;
        html += `<div class="usage-header">`;
        html += `<span class="usage-label">${escapeHtml(w.label)}</span>`;
        html += `<span class="usage-detail ${color}">${detailParts.join('  ')}</span>`;
        html += `</div>`;
        html += `<div class="progress-bar"><div class="progress-fill ${color}" style="width:${Math.min(w.used_percent, 100)}%"></div></div>`;
        html += `</div>`;
    }

    // Balance
    if (usage.balance != null) {
        html += `<div class="balance">余额: $${usage.balance.toFixed(2)}</div>`;
    }

    // Updated time
    html += `<div class="updated-at">更新时间: ${escapeHtml(usage.updated_at)}</div>`;

    html += `</div>`;
    return html;
}

function renderCompactRow(usage) {
    const name = shortName(usage.provider_name);
    let html = `<div class="compact-row">`;
    html += `<div class="compact-name"><span>${escapeHtml(name)}</span></div>`;
    html += `<div class="compact-quotas">`;

    if (usage.windows.length === 0) {
        const errText = usage.status === 'ok' ? '无数据'
            : usage.status === 'error' ? '错误'
            : '未授权';
        const errColor = usage.status === 'ok' ? '#888'
            : usage.status === 'error' ? 'var(--error)'
            : 'var(--warning-text)';
        html += `<span class="compact-error" style="color:${errColor}">${errText}</span>`;
    } else {
        for (const w of usage.windows) {
            const color = pctColor(w.used_percent);
            const label = shortLabel(w.label);
            html += `<div class="quota-row">`;
            html += `<span class="quota-label">${escapeHtml(label)}</span>`;
            html += `<div class="quota-bar"><div class="progress-fill ${color}" style="width:${Math.min(w.used_percent, 100)}%"></div></div>`;
            html += `<span class="quota-pct ${color}">${w.used_percent.toFixed(0)}%</span>`;
            html += `</div>`;
        }
    }

    if (usage.balance != null) {
        html += `<span style="color:var(--success);font-size:11px"> $${usage.balance.toFixed(2)}</span>`;
    }

    html += `</div></div>`;
    return html;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Dynamically resize the window to fit content
async function resizeToFit() {
    // Wait for layout to settle
    await new Promise(r => requestAnimationFrame(r));
    await new Promise(r => requestAnimationFrame(r));

    const rect = app.getBoundingClientRect();
    const width = compact ? 300 : 420;
    let height = Math.ceil(rect.height) + 4;
    height = Math.max(height, 80);
    height = Math.min(height, 800);

    try {
        const win = window.__TAURI__.window.getCurrentWindow();
        // Try dpi module first, fallback to window module
        const mod = window.__TAURI__.dpi || window.__TAURI__.window;
        if (mod.LogicalSize) {
            await win.setSize(new mod.LogicalSize(width, height));
        } else {
            await win.setSize({ type: 'Logical', width, height });
        }

        // Reposition to bottom-right of screen
        const monitor = await win.primaryMonitor();
        if (monitor) {
            const sW = monitor.size.width / monitor.scaleFactor;
            const sH = monitor.size.height / monitor.scaleFactor;
            const x = Math.round(sW - width - 16);
            const y = Math.round(sH - height - 60);
            if (mod.LogicalPosition) {
                await win.setPosition(new mod.LogicalPosition(Math.max(x, 0), Math.max(y, 0)));
            } else {
                await win.setPosition({ type: 'Logical', x: Math.max(x, 0), y: Math.max(y, 0) });
            }
        }
    } catch (e) {
        console.error('Failed to resize:', e);
    }
}

// Toggle compact/expanded mode
function toggleCompact() {
    compact = !compact;
    applyCompactMode();

    // Re-render with current data
    const expanded = contentEl.dataset.expanded;
    const compactData = contentEl.dataset.compact;
    contentEl.innerHTML = compact ? compactData : expanded;

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

// Right-click double detection for mode toggle
document.addEventListener('contextmenu', (e) => {
    e.preventDefault();
    const now = Date.now();
    const dx = Math.abs(e.clientX - lastRightClickX);
    const dy = Math.abs(e.clientY - lastRightClickY);

    if (now - lastRightClickTime < 500 && dx < 8 && dy < 8) {
        toggleCompact();
        lastRightClickTime = 0;
        return;
    }

    lastRightClickTime = now;
    lastRightClickX = e.clientX;
    lastRightClickY = e.clientY;
});

// Escape to hide
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        const { getCurrentWindow } = window.__TAURI__.window;
        getCurrentWindow().hide();
    }
});

// Button handlers
refreshBtn.addEventListener('click', refreshUsage);
settingsBtn.addEventListener('click', openSettings);

// Drag: title bar in expanded mode, whole panel in compact mode
titleBar.addEventListener('mousedown', (e) => {
    if (e.button === 0) {
        const { getCurrentWindow } = window.__TAURI__.window;
        getCurrentWindow().startDragging();
    }
});

app.addEventListener('mousedown', (e) => {
    if (compact && e.button === 0) {
        const { getCurrentWindow } = window.__TAURI__.window;
        getCurrentWindow().startDragging();
    }
});

async function openSettings() {
    const { WebviewWindow } = window.__TAURI__.webviewWindow;
    const settingsWin = WebviewWindow.getByLabel('settings');
    if (settingsWin) {
        await settingsWin.show();
        await settingsWin.setFocus();
    }
}

// Expose to inline handlers
window.openSettings = openSettings;

// Start
init();
