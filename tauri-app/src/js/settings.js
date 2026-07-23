// Settings window logic
import { getConfig, saveConfig, parseCurlCommand, getAvailableProviderTypes, getProviderFields, listen } from './api.js';
import { resizeToFit } from './utils.js';

let currentConfig = null;
let selectedRow = -1;

// Initialize
async function init() {
    currentConfig = await getConfig();
    renderSettings();
    setupDragRegion();

    // Listen for config requests from popup
    listen('refresh-config', async () => {
        currentConfig = await getConfig();
        renderSettings();
    });
}

// Setup drag region using JavaScript API
function setupDragRegion() {
    const dragRegion = document.querySelector('.drag-region');
    if (dragRegion) {
        dragRegion.addEventListener('mousedown', (e) => {
            if (e.button === 0) {
                window.__TAURI__.window.getCurrentWindow().startDragging();
            }
        });
    }
}

function renderSettings() {
    renderGeneralSettings();
    renderProviderTable();
    resizeToFit('app', { center: true });
}

function renderGeneralSettings() {
    const intervalInput = document.getElementById('refresh-interval');
    intervalInput.value = currentConfig.refresh_interval_seconds;
}

function renderProviderTable() {
    const tbody = document.getElementById('provider-tbody');
    tbody.innerHTML = '';

    currentConfig.providers.forEach((prov, index) => {
        const tr = document.createElement('tr');
        if (index === selectedRow) tr.classList.add('selected');

        // Enabled checkbox
        const tdEnabled = document.createElement('td');
        const checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.checked = prov.enabled;
        checkbox.addEventListener('change', () => {
            currentConfig.providers[index].enabled = checkbox.checked;
        });
        tdEnabled.appendChild(checkbox);

        // Name
        const tdName = document.createElement('td');
        tdName.textContent = prov.name;
        tdName.style.color = '#e0e0e0';

        // Type
        const tdType = document.createElement('td');
        const typeLabels = {
            zai: 'Z.ai 智谱', minimax: 'MiniMax', kimi: 'Kimi 月之暗面',
            alibaba: '阿里云百炼', openrouter: 'OpenRouter',
            baidu: '百度千帆', opencode: 'OpenCode Go', ollama: 'Ollama', custom: '自定义',
        };
        tdType.textContent = typeLabels[prov.type] || prov.type;
        tdType.style.color = '#888';

        // API Key status
        const tdKey = document.createElement('td');
        const key = prov.api_key;
        if (prov.type === 'baidu') {
            console.log('[DEBUG] render baidu:', JSON.stringify({
                type: prov.type,
                apiKey: key,
                extra_keys: Object.keys(prov.extra || {}),
                has_cookie: !!prov.extra?.cookie,
                has_csrftoken: !!prov.extra?.csrftoken,
            }));
        }
        if (key && key.length > 12) {
            tdKey.textContent = key.slice(0, 8) + '...' + key.slice(-4);
            tdKey.className = 'key-set';
        } else if (key) {
            tdKey.textContent = '已设置';
            tdKey.className = 'key-set';
        } else if ((prov.type === 'baidu' && prov.extra && (prov.extra.cookie || prov.extra.csrftoken)) ||
                   (prov.type === 'opencode' && prov.extra && (prov.extra.cookie || prov.extra.auth)) ||
                   (prov.type === 'ollama' && prov.extra && prov.extra.cookie)) {
            tdKey.textContent = '已配置';
            tdKey.className = 'key-set';
        } else {
            tdKey.textContent = '未设置';
            tdKey.className = 'key-not-set';
        }

        tr.appendChild(tdEnabled);
        tr.appendChild(tdName);
        tr.appendChild(tdType);
        tr.appendChild(tdKey);

        tr.addEventListener('click', () => {
            selectedRow = index;
            renderProviderTable();
        });

        tbody.appendChild(tr);
    });
}

// Add provider
document.getElementById('add-btn').addEventListener('click', async () => {
    const types = await getAvailableProviderTypes();
    showProviderModal(null, types);
});

// Edit provider
document.getElementById('edit-btn').addEventListener('click', async () => {
    if (selectedRow < 0 || selectedRow >= currentConfig.providers.length) return;
    const types = await getAvailableProviderTypes();
    showProviderModal(currentConfig.providers[selectedRow], types);
});

// Remove provider
document.getElementById('remove-btn').addEventListener('click', () => {
    if (selectedRow < 0 || selectedRow >= currentConfig.providers.length) return;
    const prov = currentConfig.providers[selectedRow];
    if (confirm(`确定移除 ${prov.name} 吗？`)) {
        currentConfig.providers.splice(selectedRow, 1);
        selectedRow = -1;
        renderProviderTable();
    }
});

// Close / Save
document.getElementById('close-btn').addEventListener('click', async () => {
    // Update interval
    const intervalInput = document.getElementById('refresh-interval');
    currentConfig.refresh_interval_seconds = parseInt(intervalInput.value) || 60;

    // Update enabled states from checkboxes
    // (already updated via change events)
    await saveConfig(currentConfig);
    const { getCurrentWindow } = window.__TAURI__.window;
    getCurrentWindow().hide();
});

// Provider edit modal
async function showProviderModal(existingConfig, types) {
    const overlay = document.getElementById('modal-overlay');
    const modal = document.getElementById('provider-modal');
    const typeSelect = document.getElementById('modal-type');
    const fieldsContainer = document.getElementById('modal-fields');
    const customContainer = document.getElementById('modal-custom');

    // Populate type dropdown
    typeSelect.innerHTML = '';
    for (const [typeId, typeName] of types) {
        const opt = document.createElement('option');
        opt.value = typeId;
        opt.textContent = typeName;
        typeSelect.appendChild(opt);
    }

    // Reset
    fieldsContainer.innerHTML = '';
    customContainer.style.display = 'none';
    document.getElementById('modal-title').textContent =
        existingConfig ? '编辑服务商' : '添加服务商';

    // Pre-fill if editing
    if (existingConfig) {
        typeSelect.value = existingConfig.type;
        if (existingConfig.type === 'custom') {
            customContainer.style.display = 'block';
            document.getElementById('custom-id').value = existingConfig.id;
            document.getElementById('custom-name').value = existingConfig.name;
            document.getElementById('custom-url').value = existingConfig.extra?.quota_url || '';
        } else if (existingConfig.type === 'baidu') {
            await buildFields(existingConfig.type, existingConfig);
        } else {
            await buildFields(existingConfig.type, existingConfig);
        }
    } else {
        await buildFields(typeSelect.value, null);
    }

    // Type change handler
    typeSelect.onchange = async () => {
        fieldsContainer.innerHTML = '';
        const selected = typeSelect.value;
        customContainer.style.display = selected === 'custom' ? 'block' : 'none';
        if (selected !== 'custom') {
            await buildFields(selected, null);
        }
    };

    // Show modal
    overlay.classList.add('active');

    // Save handler
    document.getElementById('modal-save').onclick = async () => {
        const typeId = typeSelect.value;
        let newConfig;

        if (typeId === 'custom') {
            const id = document.getElementById('custom-id').value.trim();
            const name = document.getElementById('custom-name').value.trim();
            const url = document.getElementById('custom-url').value.trim();
            if (!id || !name) {
                alert('服务商 ID 和名称为必填项');
                return;
            }
            const extra = { quota_url: url };
            newConfig = {
                id, type: 'custom', name, enabled: true,
                api_key: '', extra
            };
        } else {
            const extra = {};
            let apiKey = '';

            // Collect field values
            const inputs = fieldsContainer.querySelectorAll('[data-field]');
            for (const input of inputs) {
                const fieldName = input.dataset.field;
                if (fieldName === 'api_key') {
                    apiKey = input.value.trim();
                } else if (input.tagName === 'SELECT') {
                    extra[fieldName] = input.value;
                } else {
                    extra[fieldName] = input.value.trim();
                }
            }

            // curl-based providers: parse the pasted curl into auth fields
            const curlProviders = {
                baidu: ['cookie', 'csrftoken', 'x-bce-jt'],
                opencode: ['auth', 'url', 'cookie'],
                ollama: ['cookie'],
            };
            if (curlProviders[typeId]) {
                const curlInput = fieldsContainer.querySelector('[data-field="curl"]');
                if (curlInput && curlInput.value.trim()) {
                    try {
                        const parsed = await parseCurlCommand(curlInput.value.trim());
                        if (!parsed.cookie && !parsed.auth) {
                            alert('无法从 curl 命令中提取认证信息，请确保复制了正确的请求');
                            return;
                        }
                        Object.assign(extra, parsed);
                        delete extra.curl; // Don't save raw curl text to config
                    } catch (e) {
                        console.error('parseCurl error:', e);
                        alert('curl 命令解析失败: ' + e);
                        return;
                    }
                } else if (existingConfig) {
                    // Re-editing without new curl: preserve existing auth data
                    if (existingConfig.extra) {
                        for (const k of curlProviders[typeId]) {
                            if (existingConfig.extra[k]) {
                                extra[k] = existingConfig.extra[k];
                            }
                        }
                    }
                }
            }

            const typeNames = {
                zai: 'Z.ai (智谱)', minimax: 'MiniMax', kimi: 'Kimi (月之暗面)',
                alibaba: '阿里云百炼', openrouter: 'OpenRouter', baidu: '百度千帆',
                opencode: 'OpenCode Go', ollama: 'Ollama',
            };

            newConfig = {
                id: existingConfig ? existingConfig.id : typeId,
                type: typeId,
                name: existingConfig ? existingConfig.name : (typeNames[typeId] || typeId),
                enabled: existingConfig ? existingConfig.enabled : true,
                api_key: apiKey,
                extra
            };
        }

        if (existingConfig && selectedRow >= 0) {
            currentConfig.providers[selectedRow] = newConfig;
        } else {
            currentConfig.providers.push(newConfig);
        }

        console.log('[DEBUG] newConfig saved:', JSON.stringify({
            type: newConfig.type,
            api_key: newConfig.api_key,
            extra_keys: Object.keys(newConfig.extra || {}),
            has_cookie: !!newConfig.extra?.cookie,
            has_csrftoken: !!newConfig.extra?.csrftoken,
        }));

        overlay.classList.remove('active');
        renderProviderTable();
    };

    // Cancel handler
    document.getElementById('modal-cancel').onclick = () => {
        overlay.classList.remove('active');
    };
}

// Provider-specific tutorial text for obtaining the curl command.
function curlTutorial(providerType) {
    if (providerType === 'opencode') {
        return '获取 curl 命令步骤:\n\n' +
            '1. 登录 https://opencode.ai 并进入你的 workspace\n' +
            '   （浏览器地址栏形如 https://opencode.ai/workspace/wrk_xxx/go）\n' +
            '2. 按 F12 打开开发者工具，切换到 网络 (Network) 标签页\n' +
            '3. 刷新页面，在请求列表中找到名为 go 的请求\n' +
            '4. 右键该请求 → 复制 → 复制为 cURL（bash 或 cmd 均可）\n' +
            '5. 粘贴到上方文本框，保存即可\n\n' +
            '提示：opencode 的 auth 是会话 Cookie，会定期失效，过期后重新复制即可。';
    }
    if (providerType === 'ollama') {
        return '获取 curl 命令步骤:\n\n' +
            '1. 登录 https://ollama.com/settings （Usage 页面）\n' +
            '2. 按 F12 打开开发者工具，切换到 网络 (Network) 标签页\n' +
            '3. 刷新页面，在请求列表中找到名为 settings 的请求\n' +
            '4. 右键该请求 → 复制 → 复制为 cURL（bash 或 cmd 均可）\n' +
            '5. 粘贴到上方文本框，保存即可\n\n' +
            '提示：Ollama 使用 Cookie 认证，会定期失效，过期后重新复制即可。';
    }
    // baidu (default)
    return '获取 curl 命令步骤:\n\n' +
        '1. 登录 百度千帆资源订阅页面\n' +
        '2. 按 F12 打开浏览器开发者工具，切换到 网络 (Network) 标签页\n' +
        '3. 在网络请求列表中找到名为 resourceList 的请求\n' +
        '4. 右键点击该请求 → 复制 → 复制为 cURL(bash)\n' +
        '   （注意：选"复制为 cURL(bash)"，不要选"全部复制"）\n' +
        '5. 将复制的内容粘贴到上方的文本框中，点击保存即可';
}

async function buildFields(providerType, existingConfig) {
    const container = document.getElementById('modal-fields');
    container.innerHTML = '';

    const fields = await getProviderFields(providerType);

    for (const [fieldName, fieldType] of fields) {
        const div = document.createElement('div');
        div.className = 'modal-field';

        const label = document.createElement('label');
        if (fieldType === 'password') {
            label.textContent = 'API 密钥';
        } else if (fieldType === 'textarea') {
            label.textContent = 'curl 命令';
        } else {
            label.textContent = fieldName.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
        }
        div.appendChild(label);

        if (fieldType.startsWith('select:')) {
            const select = document.createElement('select');
            select.dataset.field = fieldName;
            const options = fieldType.split(':')[1].split(',');
            const regionLabels = { china: '国内', global: '国际' };
            for (const opt of options) {
                const option = document.createElement('option');
                option.value = opt;
                option.textContent = regionLabels[opt] || opt;
                select.appendChild(option);
            }

            // Pre-fill
            if (existingConfig) {
                const val = existingConfig.extra?.[fieldName];
                if (val) select.value = val;
            }
            div.appendChild(select);
        } else if (fieldType === 'textarea') {
            const textarea = document.createElement('textarea');
            textarea.dataset.field = fieldName;
            const placeholders = {
                baidu: '粘贴 resourceList 请求的 curl 命令（复制为 cURL(bash)）...',
                opencode: '粘贴 workspace .../go 页面的 curl 命令（复制为 cURL，bash/cmd 均可）...',
                ollama: '粘贴 ollama.com/settings 页面的 curl 命令（复制为 cURL，bash/cmd 均可）...',
            };
            textarea.placeholder = placeholders[providerType] || '粘贴 curl 命令...';

            // Existing config: show "already configured" hint instead of the raw curl
            if (existingConfig) {
                const hasConfig = providerType === 'opencode'
                    ? (existingConfig.extra?.cookie || existingConfig.extra?.auth)
                    : providerType === 'ollama'
                    ? !!existingConfig.extra?.cookie
                    : (existingConfig.extra?.cookie || existingConfig.extra?.csrftoken);
                if (hasConfig) {
                    textarea.placeholder = '已有配置。如需更新，粘贴新的 curl 命令覆盖即可。';
                }
            }

            div.appendChild(textarea);

            // Help link with provider-specific tutorial
            if (providerType === 'baidu' || providerType === 'opencode' || providerType === 'ollama') {
                const help = document.createElement('span');
                help.className = 'help-link';
                help.textContent = '如何获取 curl 命令？';
                help.onclick = () => alert(curlTutorial(providerType));
                div.appendChild(help);
            }
        } else {
            const input = document.createElement('input');
            input.dataset.field = fieldName;
            if (fieldType === 'password') {
                input.type = 'password';
                input.placeholder = '请输入 API 密钥...';
            }

            // Pre-fill
            if (existingConfig) {
                if (fieldName === 'api_key') {
                    input.value = existingConfig.api_key || '';
                } else {
                    input.value = existingConfig.extra?.[fieldName] || '';
                }
            }
            div.appendChild(input);
        }

        container.appendChild(div);
    }
}

// Start
init();
