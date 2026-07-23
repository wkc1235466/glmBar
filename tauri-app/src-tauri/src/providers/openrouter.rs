use crate::providers::models::*;
use crate::providers::Provider;
use std::future::Future;
use std::pin::Pin;

pub struct OpenRouterProvider {
    client: reqwest::Client,
    api_key: String,
}

impl OpenRouterProvider {
    pub fn new(client: reqwest::Client, api_key: &str) -> Self {
        Self {
            client,
            api_key: api_key.to_string(),
        }
    }
}

impl Provider for OpenRouterProvider {
    fn fetch_usage(&self) -> Pin<Box<dyn Future<Output = UsageData> + Send + '_>> {
        Box::pin(async move {
        if self.api_key.is_empty() {
            return UsageData::no_api_key("openrouter", "OpenRouter");
        }

        let auth_header = format!("Bearer {}", self.api_key);

        // Fetch credits
        let credits_resp = match self.client
            .get("https://openrouter.ai/api/v1/credits")
            .header("Authorization", &auth_header)
            .header("Accept", "application/json")
            .timeout(std::time::Duration::from_secs(15))
            .send()
            .await
        {
            Ok(r) => r,
            Err(e) => return UsageData::error("openrouter", "OpenRouter", &e.to_string()),
        };

        if credits_resp.status() == reqwest::StatusCode::UNAUTHORIZED {
            return UsageData::unauthorized("openrouter", "OpenRouter", "API 密钥无效");
        }

        let credits: serde_json::Value = match credits_resp.json().await {
            Ok(d) => d,
            Err(e) => return UsageData::error("openrouter", "OpenRouter", &e.to_string()),
        };

        // Fetch key info
        let key_data: serde_json::Value = match self.client
            .get("https://openrouter.ai/api/v1/key")
            .header("Authorization", &auth_header)
            .header("Accept", "application/json")
            .timeout(std::time::Duration::from_secs(15))
            .send()
            .await
        {
            Ok(r) if r.status() == reqwest::StatusCode::OK => r.json().await.unwrap_or(serde_json::json!({})),
            _ => serde_json::json!({}),
        };

        let total_credits = credits
            .get("total_credits")
            .and_then(|v| v.as_f64())
            .unwrap_or(0.0);
        let total_usage = credits
            .get("total_usage")
            .and_then(|v| v.as_f64())
            .unwrap_or(0.0);
        let balance = total_credits - total_usage;

        let mut windows: Vec<UsageWindow> = Vec::new();

        if total_credits > 0.0 {
            let pct = (total_usage / total_credits) * 100.0;
            windows.push(UsageWindow {
                label: "额度用量".into(),
                used_percent: pct.min(100.0),
                used: total_usage,
                total: total_credits,
                remaining: balance,
                resets_at: None,
                unit: "USD".into(),
            });
        }

        // Rate limit from key data
        if let Some(limit) = key_data
            .get("limit")
            .or(key_data.get("rate_limit"))
            .and_then(|v| v.as_object())
        {
            let req_limit = limit
                .get("requests")
                .and_then(|v| v.as_f64())
                .unwrap_or(0.0);
            let req_used = limit.get("usage").and_then(|v| v.as_f64()).unwrap_or(0.0);
            if req_limit > 0.0 {
                windows.push(UsageWindow {
                    label: "速率限制".into(),
                    used_percent: ((req_used / req_limit) * 100.0).min(100.0),
                    used: req_used,
                    total: req_limit,
                    remaining: req_limit - req_used,
                    resets_at: None,
                    unit: "requests".into(),
                });
            }
        }

        let is_empty = windows.is_empty();
        UsageData {
            provider_id: "openrouter".into(),
            provider_name: "OpenRouter".into(),
            status: if is_empty {
                ProviderStatus::Error
            } else {
                ProviderStatus::Ok
            },
            plan_name: "OpenRouter".into(),
            windows,
            balance: Some(balance),
                plan_expires: None,
            error_message: if is_empty {
                "未找到额度数据".into()
            } else {
                String::new()
            },
            updated_at: UsageData::now_timestamp(),
        }
        })
    }
}
