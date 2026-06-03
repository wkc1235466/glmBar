use crate::config::models::AppConfig;
use crate::config::store;
use crate::curl_parser;
use crate::providers;
use crate::providers::models::UsageData;
use std::collections::HashMap;
use tauri::{Emitter, Manager, State};

pub struct AppState {
    pub config: tokio::sync::Mutex<AppConfig>,
    pub http_client: reqwest::Client,
}

#[tauri::command]
pub async fn get_config(state: State<'_, AppState>) -> Result<AppConfig, String> {
    let config = state.config.lock().await;
    Ok(config.clone())
}

#[tauri::command]
pub async fn save_config(
    state: State<'_, AppState>,
    app: tauri::AppHandle,
    config: AppConfig,
) -> Result<(), String> {
    let mut cfg = state.config.lock().await;
    *cfg = config.clone();
    store::save_config(&cfg);
    drop(cfg); // Release lock before emitting event
    let _ = app.emit("trigger-refresh", ());
    Ok(())
}

#[tauri::command]
pub async fn fetch_all_usage(state: State<'_, AppState>) -> Result<Vec<UsageData>, String> {
    let (provider_configs, client) = {
        let config = state.config.lock().await;
        let pcs: Vec<_> = config.providers.iter()
            .filter(|p| p.enabled)
            .cloned()
            .collect();
        (pcs, state.http_client.clone())
    };

    let mut handles = Vec::new();
    for pc in &provider_configs {
        let provider = providers::create_provider(pc, &client);
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

#[tauri::command]
pub async fn show_settings_window(app: tauri::AppHandle) -> Result<(), String> {
    if let Some(window) = app.get_webview_window("settings") {
        window.show().map_err(|e| e.to_string())?;
        window.set_focus().map_err(|e| e.to_string())?;
        let _ = app.emit("refresh-config", ());
    }
    Ok(())
}
