use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "snake_case")]
pub enum ProviderStatus {
    Ok,
    Error,
    NoApiKey,
    Unauthorized,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct UsageWindow {
    pub label: String,
    pub used_percent: f64,
    #[serde(default)]
    pub used: f64,
    #[serde(default)]
    pub total: f64,
    #[serde(default)]
    pub remaining: f64,
    #[serde(default)]
    pub resets_at: Option<String>,
    #[serde(default)]
    pub unit: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct UsageData {
    pub provider_id: String,
    pub provider_name: String,
    pub status: ProviderStatus,
    #[serde(default)]
    pub plan_name: String,
    #[serde(default)]
    pub windows: Vec<UsageWindow>,
    #[serde(default)]
    pub balance: Option<f64>,
    #[serde(default)]
    pub plan_expires: Option<String>,
    #[serde(default)]
    pub error_message: String,
    #[serde(default)]
    pub updated_at: String,
}

impl UsageData {
    pub fn no_api_key(provider_id: &str, provider_name: &str) -> Self {
        Self {
            provider_id: provider_id.into(),
            provider_name: provider_name.into(),
            status: ProviderStatus::NoApiKey,
            plan_name: String::new(),
            windows: vec![],
            balance: None,
            plan_expires: None,
            error_message: String::new(),
            updated_at: chrono::Local::now().format("%H:%M:%S").to_string(),
        }
    }

    pub fn unauthorized(provider_id: &str, provider_name: &str, msg: &str) -> Self {
        Self {
            provider_id: provider_id.into(),
            provider_name: provider_name.into(),
            status: ProviderStatus::Unauthorized,
            plan_name: String::new(),
            windows: vec![],
            balance: None,
            plan_expires: None,
            error_message: msg.into(),
            updated_at: chrono::Local::now().format("%H:%M:%S").to_string(),
        }
    }

    pub fn error(provider_id: &str, provider_name: &str, msg: &str) -> Self {
        Self {
            provider_id: provider_id.into(),
            provider_name: provider_name.into(),
            status: ProviderStatus::Error,
            plan_name: String::new(),
            windows: vec![],
            balance: None,
            plan_expires: None,
            error_message: msg.into(),
            updated_at: chrono::Local::now().format("%H:%M:%S").to_string(),
        }
    }

    pub fn now_timestamp() -> String {
        chrono::Local::now().format("%H:%M:%S").to_string()
    }
}
