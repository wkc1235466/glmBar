// Tauri IPC wrapper
const { invoke } = window.__TAURI__.core;
const { listen } = window.__TAURI__.event;

export async function getConfig() {
    return invoke('get_config');
}

export async function saveConfig(config) {
    return invoke('save_config', { config });
}

export async function fetchAllUsage() {
    return invoke('fetch_all_usage');
}

export async function parseCurlCommand(curlText) {
    return invoke('parse_curl_command', { curlText });
}

export async function getAvailableProviderTypes() {
    return invoke('get_available_provider_types');
}

export async function getProviderFields(providerType) {
    return invoke('get_provider_fields', { providerType });
}

export { listen };
