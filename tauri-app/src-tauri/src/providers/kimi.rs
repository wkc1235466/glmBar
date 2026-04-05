use crate::providers::models::*;
use crate::providers::Provider;
use std::future::Future;
use std::pin::Pin;

pub struct KimiProvider {
    client: reqwest::Client,
    api_key: String,
}

impl KimiProvider {
    pub fn new(client: reqwest::Client, api_key: &str) -> Self {
        Self {
            client,
            api_key: api_key.to_string(),
        }
    }
}

impl Provider for KimiProvider {
    fn fetch_usage(&self) -> Pin<Box<dyn Future<Output = UsageData> + Send + '_>> {
        Box::pin(async move {
        if self.api_key.is_empty() {
            return UsageData::no_api_key("kimi", "Kimi (月之暗面)");
        }

        let url = "https://www.kimi.com/apiv2/kimi.gateway.billing.v1.BillingService/GetUsages";

        let resp = match self.client
            .post(url)
            .header("Authorization", format!("Bearer {}", self.api_key))
            .header("Content-Type", "application/json")
            .header("Accept", "application/json")
            .json(&serde_json::json!({}))
            .timeout(std::time::Duration::from_secs(15))
            .send()
            .await
        {
            Ok(r) => r,
            Err(e) => return UsageData::error("kimi", "Kimi (月之暗面)", &e.to_string()),
        };

        if resp.status() == reqwest::StatusCode::UNAUTHORIZED {
            return UsageData::unauthorized("kimi", "Kimi (月之暗面)", "认证令牌无效或已过期");
        }

        let data: serde_json::Value = match resp.json().await {
            Ok(d) => d,
            Err(e) => return UsageData::error("kimi", "Kimi (月之暗面)", &e.to_string()),
        };

        let mut windows: Vec<UsageWindow> = Vec::new();

        if let Some(usages) = data.get("usages").and_then(|v| v.as_array()) {
            for entry in usages {
                if entry.get("scope").and_then(|v| v.as_str()) != Some("FEATURE_CODING") {
                    continue;
                }

                // Primary: weekly quota
                if let Some(detail) = entry.get("detail") {
                    let limit = detail.get("limit").and_then(|v| v.as_f64()).unwrap_or(0.0);
                    let used = detail.get("used").and_then(|v| v.as_f64()).unwrap_or(0.0);
                    let remaining = detail
                        .get("remaining")
                        .and_then(|v| v.as_f64())
                        .unwrap_or(0.0);
                    let reset_time = detail
                        .get("resetTime")
                        .and_then(|v| v.as_str())
                        .unwrap_or("");

                    if limit > 0.0 {
                        windows.push(UsageWindow {
                            label: "每周配额".into(),
                            used_percent: ((used / limit) * 100.0).min(100.0),
                            used,
                            total: limit,
                            remaining,
                            resets_at: if reset_time.is_empty() {
                                None
                            } else {
                                Some(reset_time.replace('Z', "+00:00"))
                            },
                            unit: "requests".into(),
                        });
                    }
                }

                // Secondary: rate limits
                if let Some(limits) = entry.get("limits").and_then(|v| v.as_array()) {
                    for sub in limits {
                        let sub_detail = sub.get("detail").cloned().unwrap_or(serde_json::json!({}));
                        let sub_limit = sub_detail
                            .get("limit")
                            .and_then(|v| v.as_f64())
                            .unwrap_or(0.0);
                        let sub_used = sub_detail
                            .get("used")
                            .and_then(|v| v.as_f64())
                            .unwrap_or(0.0);
                        let sub_remaining = sub_detail
                            .get("remaining")
                            .and_then(|v| v.as_f64())
                            .unwrap_or(0.0);
                        let sub_reset = sub_detail
                            .get("resetTime")
                            .and_then(|v| v.as_str())
                            .unwrap_or("");

                        if sub_limit > 0.0 {
                            let duration = sub
                                .get("window")
                                .and_then(|w| w.get("duration"))
                                .and_then(|v| v.as_i64())
                                .unwrap_or(300);
                            let label = if duration >= 60 {
                                format!("{}小时限流", duration / 60)
                            } else {
                                format!("{}分钟限流", duration)
                            };

                            windows.push(UsageWindow {
                                label,
                                used_percent: ((sub_used / sub_limit) * 100.0).min(100.0),
                                used: sub_used,
                                total: sub_limit,
                                remaining: sub_remaining,
                                resets_at: if sub_reset.is_empty() {
                                    None
                                } else {
                                    Some(sub_reset.replace('Z', "+00:00"))
                                },
                                unit: "requests".into(),
                            });
                        }
                    }
                }
            }
        }

        let is_empty = windows.is_empty();
        UsageData {
            provider_id: "kimi".into(),
            provider_name: "Kimi (月之暗面)".into(),
            status: if is_empty {
                ProviderStatus::Error
            } else {
                ProviderStatus::Ok
            },
            plan_name: "Kimi 编程版".into(),
            windows,
            balance: None,
            error_message: if is_empty {
                "未找到编程用量数据".into()
            } else {
                String::new()
            },
            updated_at: UsageData::now_timestamp(),
        }
        })
    }
}
