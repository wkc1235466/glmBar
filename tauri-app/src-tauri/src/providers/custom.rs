use crate::providers::models::*;
use crate::providers::Provider;
use async_trait::async_trait;

pub struct CustomProvider {
    provider_id: String,
    name: String,
    api_key: String,
    quota_url: String,
}

impl CustomProvider {
    pub fn new(id: &str, name: &str, api_key: &str, quota_url: Option<&str>) -> Self {
        Self {
            provider_id: id.to_string(),
            name: name.to_string(),
            api_key: api_key.to_string(),
            quota_url: quota_url.unwrap_or("").to_string(),
        }
    }
}

#[async_trait]
impl Provider for CustomProvider {
    async fn fetch_usage(&self) -> UsageData {
        if self.api_key.is_empty() {
            return UsageData::no_api_key(&self.provider_id, &self.name);
        }

        if self.quota_url.is_empty() {
            return UsageData::error(&self.provider_id, &self.name, "未配置配额查询 URL");
        }

        let client = reqwest::Client::new();
        let resp = match client
            .get(&self.quota_url)
            .header("Authorization", format!("Bearer {}", self.api_key))
            .header("Accept", "application/json")
            .timeout(std::time::Duration::from_secs(15))
            .send()
            .await
        {
            Ok(r) => r,
            Err(e) => return UsageData::error(&self.provider_id, &self.name, &e.to_string()),
        };

        let data: serde_json::Value = match resp.json().await {
            Ok(d) => d,
            Err(e) => return UsageData::error(&self.provider_id, &self.name, &e.to_string()),
        };

        // Try common patterns
        let mut windows: Vec<UsageWindow> = Vec::new();

        for key in &["data", "usage", "quota", "limits"] {
            if let Some(entry) = data.get(*key) {
                if entry.is_object() {
                    let used = entry
                        .get("used")
                        .or(entry.get("usage"))
                        .and_then(|v| v.as_f64())
                        .unwrap_or(0.0);
                    let total = entry
                        .get("total")
                        .or(entry.get("limit"))
                        .or(entry.get("quota"))
                        .and_then(|v| v.as_f64())
                        .unwrap_or(0.0);
                    if total > 0.0 {
                        windows.push(UsageWindow {
                            label: "Usage".into(),
                            used_percent: ((used / total) * 100.0).min(100.0),
                            used,
                            total,
                            remaining: total - used,
                            resets_at: None,
                            unit: String::new(),
                        });
                    }
                    break;
                } else if entry.is_array() {
                    for item in entry.as_array().unwrap().iter().take(3) {
                        let used = item
                            .get("used")
                            .or(item.get("usage"))
                            .and_then(|v| v.as_f64())
                            .unwrap_or(0.0);
                        let total = item
                            .get("total")
                            .or(item.get("limit"))
                            .or(item.get("number"))
                            .and_then(|v| v.as_f64())
                            .unwrap_or(0.0);
                        let label = item
                            .get("type")
                            .or(item.get("label"))
                            .and_then(|v| v.as_str())
                            .unwrap_or("Usage")
                            .to_string();
                        if total > 0.0 {
                            windows.push(UsageWindow {
                                label,
                                used_percent: ((used / total) * 100.0).min(100.0),
                                used,
                                total,
                                remaining: total - used,
                                resets_at: None,
                                unit: String::new(),
                            });
                        }
                    }
                    break;
                }
            }
        }

        let is_empty = windows.is_empty();
        UsageData {
            provider_id: self.provider_id.clone(),
            provider_name: self.name.clone(),
            status: if is_empty {
                ProviderStatus::Error
            } else {
                ProviderStatus::Ok
            },
            plan_name: String::new(),
            windows,
            balance: None,
            error_message: if is_empty {
                "无法解析响应中的用量数据".into()
            } else {
                String::new()
            },
            updated_at: UsageData::now_timestamp(),
        }
    }
}
