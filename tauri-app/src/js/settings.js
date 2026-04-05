// Settings window logic
import { getConfig, saveConfig, parseCurlCommand, getAvailableProviderTypes, getProviderFields, listen } from './api.js';
import { resizeToFit } from './utils.js';

let currentConfig = null;
let selectedRow = -1;

// Initialize
async function init() {
    currentConfig = await getConfig();
    renderSettings();

    // Listen for config requests from popup
    listen('refresh-config', async () => {
        currentConfig = await getConfig();
        renderSettings();
    });
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
            baidu: '百度千帆', custom: '自定义',
        };
        tdType.textContent = typeLabels[prov.type] || prov.type;
        tdType.style.color = '#888';

        // API Key status
        const tdKey = document.createElement('td');
        const key = prov.api_key;
        if (key && key.length > 12) {
            tdKey.textContent = key.slice(0, 8) + '...' + key.slice(-4);
            tdKey.className = 'key-set';
        } else if (key) {
            tdKey.textContent = '已设置';
            tdKey.className = 'key-set';
        } else if (prov.type === 'baidu' && prov.extra && (prov.extra.cookie || prov.extra.csrftoken)) {
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

            // Baidu curl parsing
            if (typeId === 'baidu') {
                const curlInput = fieldsContainer.querySelector('[data-field="curl"]');
                if (curlInput && curlInput.value.trim()) {
                    const parsed = await parseCurlCommand(curlInput.value.trim());
                    if (Object.keys(parsed).length === 0) {
                        alert('无法从 curl 命令中提取认证信息');
                        return;
                    }
                    Object.assign(extra, parsed);
                }
            }

            const typeNames = {
                zai: 'Z.ai (智谱)', minimax: 'MiniMax', kimi: 'Kimi (月之暗面)',
                alibaba: '阿里云百炼', openrouter: 'OpenRouter', baidu: '百度千帆',
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

        overlay.classList.remove('active');
        renderProviderTable();
    };

    // Cancel handler
    document.getElementById('modal-cancel').onclick = () => {
        overlay.classList.remove('active');
    };
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
            textarea.placeholder = '粘贴浏览器中复制的 curl 命令...';

            // Baidu: show placeholder for existing config
            if (existingConfig && providerType === 'baidu') {
                const hasConfig = existingConfig.extra?.cookie || existingConfig.extra?.csrftoken;
                if (hasConfig) {
                    textarea.placeholder = '已有配置。如需更新，粘贴新的 curl 命令覆盖即可。';
                }
            }

            div.appendChild(textarea);

            // Baidu: add help text
            if (providerType === 'baidu') {
                const help = document.createElement('span');
                help.className = 'help-link';
                help.textContent = '如何获取 curl 命令？';
                help.onclick = () => alert(
                    '获取 curl 命令步骤:\n\n' +
                    '1. 登录 百度千帆资源订阅页面\n' +
                    '2. 按 F12 打开浏览器开发者工具，切换到 网络 (Network) 标签页\n' +
                    '3. 点击页面中的 刷新按钮\n' +
                    '4. 在网络请求列表中找到名为 resourceList 的请求\n' +
                    '5. 右键点击该请求 → 复制 → 复制为 cURL(bash)\n' +
                    '6. 将复制的内容粘贴到上方的文本框中，点击保存即可'
                );
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
