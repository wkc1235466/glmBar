use crate::providers::models::*;
use crate::providers::Provider;
use reqwest::header::{HeaderMap, HeaderValue, ACCEPT, AUTHORIZATION};
use std::future::Future;
use std::pin::Pin;

pub struct MiniMaxProvider {
    client: reqwest::Client,
    api_key: String,
    region: String,
}

impl MiniMaxProvider {
    pub fn new(client: reqwest::Client, api_key: &str, region: Option<&str>) -> Self {
        Self {
            client,
            api_key: api_key.to_string(),
            region: region.unwrap_or("china").to_string(),
        }
    }

    fn base_url(&self) -> String {
        match self.region.as_str() {
            "china" => "https://platform.minimaxi.com".to_string(),
            "global" => "https://platform.minimax.io".to_string(),
            other if other.starts_with("http") => other.to_string(),
            other => format!("https://{}", other),
        }
    }

    fn build_headers(&self) -> HeaderMap {
        let mut headers = HeaderMap::new();
        headers.insert(
            AUTHORIZATION,
            HeaderValue::from_str(&format!("Bearer {}", self.api_key)).unwrap_or_else(|_| HeaderValue::from_static("")),
        );
        headers.insert(ACCEPT, HeaderValue::from_static("application/json"));
        headers
    }
}

impl Provider for MiniMaxProvider {
    fn fetch_usage(&self) -> Pin<Box<dyn Future<Output = UsageData> + Send + '_>> {
        Box::pin(async move {
        if self.api_key.is_empty() {
            return UsageData::no_api_key("minimax", "MiniMax");
        }

        let headers = self.build_headers();

        // Primary endpoint
        let primary_url = "https://api.minimax.io/v1/coding_plan/remains";
        let resp = self.client
            .get(primary_url)
            .headers(headers.clone())
            .timeout(std::time::Duration::from_secs(15))
            .send()
            .await;

        let resp = match resp {
            Ok(r) => r,
            Err(_) => {
                // Fallback
                let fallback_url = format!(
                    "{}/v1/api/openplatform/coding_plan/remains",
                    self.base_url()
                );
                match self.client
                    .get(&fallback_url)
                    .headers(headers)
                    .timeout(std::time::Duration::from_secs(15))
                    .send()
                    .await
                {
                    Ok(r) => r,
                    Err(e) => return UsageData::error("minimax", "MiniMax", &e.to_string()),
                }
            }
        };

        if resp.status() == reqwest::StatusCode::UNAUTHORIZED {
            return UsageData::unauthorized("minimax", "MiniMax", "API 密钥无效或已过期");
        }

        let data: serde_json::Value = match resp.json().await {
            Ok(d) => d,
            Err(e) => return UsageData::error("minimax", "MiniMax", &e.to_string()),
        };

        let model_remains = data
            .get("model_remains")
            .or(data.get("data"))
            .cloned()
            .unwrap_or(serde_json::json!(null));

        let model = if model_remains.is_array() {
            model_remains
                .as_array()
                .and_then(|a| a.first())
                .cloned()
                .unwrap_or(serde_json::json!({}))
        } else {
            model_remains
        };

        let mut windows: Vec<UsageWindow> = Vec::new();

        let total = model.get("total").and_then(|v| v.as_f64()).unwrap_or(0.0);
        let used = model.get("used").and_then(|v| v.as_f64()).unwrap_or(0.0);
        let remaining = model.get("remaining").and_then(|v| v.as_f64()).unwrap_or(0.0);

        if total > 0.0 {
            let pct = (used / total) * 100.0;
            windows.push(UsageWindow {
                label: "用量配额".into(),
                used_percent: pct.min(100.0),
                used,
                total,
                remaining,
                resets_at: None,
                unit: "units".into(),
            });
        }

        let plan_name = data
            .get("plan_name")
            .or(data.get("planName"))
            .and_then(|v| v.as_str())
            .unwrap_or("")
            .to_string();

        let is_empty = windows.is_empty();
        UsageData {
            provider_id: "minimax".into(),
            provider_name: "MiniMax".into(),
            status: if is_empty {
                ProviderStatus::Error
            } else {
                ProviderStatus::Ok
            },
            plan_name,
            windows,
            balance: None,
            error_message: if is_empty {
                "未找到用量数据".into()
            } else {
                String::new()
            },
            updated_at: UsageData::now_timestamp(),
        }
        })
    }
}
