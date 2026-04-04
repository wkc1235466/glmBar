use serde::{Deserialize, Serialize};
use std::collections::HashMap;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProviderConfig {
    pub id: String,
    #[serde(rename = "type")]
    pub provider_type: String,
    pub name: String,
    #[serde(default = "default_true")]
    pub enabled: bool,
    #[serde(default)]
    pub api_key: String,
    #[serde(default)]
    pub extra: HashMap<String, String>,
}

fn default_true() -> bool {
    true
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AppConfig {
    #[serde(default = "default_refresh_interval")]
    pub refresh_interval_seconds: u64,
    #[serde(default)]
    pub providers: Vec<ProviderConfig>,
    #[serde(default = "default_true")]
    pub always_on_top: bool,
    #[serde(default)]
    pub show_window_on_start: bool,
    #[serde(default)]
    pub compact_mode: bool,
}

fn default_refresh_interval() -> u64 {
    60
}

impl Default for AppConfig {
    fn default() -> Self {
        Self {
            refresh_interval_seconds: 60,
            providers: vec![
                ProviderConfig {
                    id: "zai".into(),
                    provider_type: "zai".into(),
                    name: "Z.ai (智谱)".into(),
                    enabled: true,
                    api_key: String::new(),
                    extra: HashMap::new(),
                },
                ProviderConfig {
                    id: "minimax".into(),
                    provider_type: "minimax".into(),
                    name: "MiniMax".into(),
                    enabled: true,
                    api_key: String::new(),
                    extra: HashMap::new(),
                },
                ProviderConfig {
                    id: "kimi".into(),
                    provider_type: "kimi".into(),
                    name: "Kimi (月之暗面)".into(),
                    enabled: true,
                    api_key: String::new(),
                    extra: HashMap::new(),
                },
                ProviderConfig {
                    id: "alibaba".into(),
                    provider_type: "alibaba".into(),
                    name: "阿里云百炼".into(),
                    enabled: true,
                    api_key: String::new(),
                    extra: HashMap::new(),
                },
                ProviderConfig {
                    id: "openrouter".into(),
                    provider_type: "openrouter".into(),
                    name: "OpenRouter".into(),
                    enabled: true,
                    api_key: String::new(),
                    extra: HashMap::new(),
                },
                ProviderConfig {
                    id: "baidu".into(),
                    provider_type: "baidu".into(),
                    name: "百度千帆".into(),
                    enabled: true,
                    api_key: String::new(),
                    extra: HashMap::new(),
                },
            ],
            always_on_top: true,
            show_window_on_start: false,
            compact_mode: false,
        }
    }
}
