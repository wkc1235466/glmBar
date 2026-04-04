use crate::config::models::AppConfig;
use crate::config::store;
use crate::curl_parser;
use crate::providers;
use crate::providers::models::UsageData;
use std::collections::HashMap;
use tauri::State;

pub struct AppState {
    pub config: tokio::sync::Mutex<AppConfig>,
}

#[tauri::command]
pub async fn get_config(state: State<'_, AppState>) -> Result<AppConfig, String> {
    let config = state.config.lock().await;
    Ok(config.clone())
}

#[tauri::command]
pub async fn save_config(
    state: State<'_, AppState>,
    config: AppConfig,
) -> Result<(), String> {
    let mut cfg = state.config.lock().await;
    *cfg = config.clone();
    store::save_config(&cfg);
    Ok(())
}

#[tauri::command]
pub async fn fetch_all_usage(state: State<'_, AppState>) -> Result<Vec<UsageData>, String> {
    // Clone provider configs and drop lock before making HTTP requests
    let provider_configs: Vec<_> = {
        let config = state.config.lock().await;
        config.providers.iter()
            .filter(|p| p.enabled)
            .cloned()
            .collect()
    }; // lock dropped here

    let mut handles = Vec::new();
    for pc in &provider_configs {
        let provider = providers::create_provider(pc);
        handles.push(tokio::spawn(async move { provider.fetch_usage().await }));
    }

    let mut results = Vec::new();
    for handle in handles {
        match handle.await {
            Ok(data) => results.push(data),
            Err(e) => results.push(UsageData::error("unknown", "Unknown", &e.to_string())),
        }
    }
    Ok(results)
}

#[tauri::command]
pub async fn parse_curl_command(curl_text: String) -> Result<HashMap<String, String>, String> {
    let result = curl_parser::parse_curl(&curl_text);
    Ok(result)
}

#[tauri::command]
pub fn get_available_provider_types() -> Result<Vec<(String, String)>, String> {
    let types = vec![
        ("zai".into(), "Z.ai (智谱)".into()),
        ("minimax".into(), "MiniMax".into()),
        ("kimi".into(), "Kimi (月之暗面)".into()),
        ("alibaba".into(), "阿里云百炼".into()),
        ("openrouter".into(), "OpenRouter".into()),
        ("baidu".into(), "百度千帆".into()),
        ("custom".into(), "自定义".into()),
    ];
    Ok(types)
}

#[tauri::command]
pub fn get_provider_fields(provider_type: String) -> Result<Vec<(String, String)>, String> {
    Ok(providers::get_display_config(&provider_type))
}
