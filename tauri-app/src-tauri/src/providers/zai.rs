use crate::providers::models::*;
use crate::providers::Provider;
use std::future::Future;
use std::pin::Pin;

pub struct ZaiProvider {
    client: reqwest::Client,
    api_key: String,
    region: String,
}

impl ZaiProvider {
    pub fn new(client: reqwest::Client, api_key: &str, region: Option<&str>) -> Self {
        Self {
            client,
            api_key: api_key.to_string(),
            region: region.unwrap_or("china").to_string(),
        }
    }

    fn base_url(&self) -> String {
        match self.region.as_str() {
            "china" => "https://open.bigmodel.cn".to_string(),
            "global" => "https://api.z.ai".to_string(),
            other if other.starts_with("http") => other.to_string(),
            other => format!("https://{}", other),
        }
    }
}

impl Provider for ZaiProvider {
    fn fetch_usage(&self) -> Pin<Box<dyn Future<Output = UsageData> + Send + '_>> {
        Box::pin(async move {
        if self.api_key.is_empty() {
            return UsageData::no_api_key("zai", "Z.ai (智谱)");
        }

        let url = format!("{}/api/monitor/usage/quota/limit", self.base_url());

        let resp = match self.client
            .get(&url)
            .header("Authorization", format!("Bearer {}", self.api_key))
            .header("Accept", "application/json")
            .timeout(std::time::Duration::from_secs(15))
            .send()
            .await
        {
            Ok(r) => r,
            Err(e) => return UsageData::error("zai", "Z.ai (智谱)", &e.to_string()),
        };

        if resp.status() == reqwest::StatusCode::UNAUTHORIZED {
            return UsageData::unauthorized("zai", "Z.ai (智谱)", "API 密钥无效或已过期");
        }

        let data: serde_json::Value = match resp.json().await {
            Ok(d) => d,
            Err(e) => return UsageData::error("zai", "Z.ai (智谱)", &e.to_string()),
        };

        let code = data.get("code").and_then(|v| v.as_i64()).unwrap_or(-1);
        if code != 200 {
            let msg = data
                .get("msg")
                .and_then(|v| v.as_str())
                .unwrap_or("未知错误");
            return UsageData::error("zai", "Z.ai (智谱)", &format!("API 错误: {}", msg));
        }

        let payload = data.get("data").cloned().unwrap_or(serde_json::json!({}));
        let plan_name = payload
            .get("planName")
            .or(payload.get("plan"))
            .or(payload.get("packageName"))
            .and_then(|v| v.as_str())
            .unwrap_or("")
            .to_string();

        let mut windows: Vec<UsageWindow> = Vec::new();

        if let Some(limits) = payload.get("limits").and_then(|v| v.as_array()) {
            for limit in limits {
                let limit_type = limit
                    .get("type")
                    .and_then(|v| v.as_str())
                    .unwrap_or("")
                    .to_string();
                let usage = limit.get("usage").and_then(|v| v.as_f64()).unwrap_or(0.0);
                let number = limit.get("number").and_then(|v| v.as_f64()).unwrap_or(0.0);
                let remaining = limit
                    .get("remaining")
                    .and_then(|v| v.as_f64())
                    .unwrap_or(0.0);
                let current_value = limit
                    .get("currentValue")
                    .and_then(|v| v.as_f64())
                    .unwrap_or(usage);
                let percentage = limit.get("percentage").and_then(|v| v.as_f64());

                let pct = percentage
                    .unwrap_or_else(|| if number > 0.0 { (current_value / number) * 100.0 } else { 0.0 });

                let resets_at = limit
                    .get("nextResetTime")
                    .and_then(|v| v.as_i64())
                    .map(|ms| {
                        chrono::DateTime::from_timestamp_millis(ms)
                            .map(|dt| dt.format("%Y-%m-%dT%H:%M:%S%:z").to_string())
                            .unwrap_or_default()
                    });

                let (label, unit) = if limit_type == "TIME_LIMIT" {
                    ("MCP/时间配额".to_string(), "次".to_string())
                } else {
                    ("Token 配额".to_string(), "tokens".to_string())
                };

                windows.push(UsageWindow {
                    label,
                    used_percent: pct.min(100.0),
                    used: current_value,
                    total: number,
                    remaining,
                    resets_at,
                    unit,
                });
            }
        }

        // Token 配额排在前面
        windows.sort_by(|a, b| {
            let a_has_token = a.label.contains("Token") as i32;
            let b_has_token = b.label.contains("Token") as i32;
            b_has_token.cmp(&a_has_token)
        });

        let is_empty = windows.is_empty();
        UsageData {
            provider_id: "zai".into(),
            provider_name: "Z.ai (智谱)".into(),
            status: if is_empty {
                ProviderStatus::Error
            } else {
                ProviderStatus::Ok
            },
            plan_name,
            windows,
            balance: None,
            error_message: if is_empty {
                "未找到配额数据".into()
            } else {
                String::new()
            },
            updated_at: UsageData::now_timestamp(),
        }
        })
    }
}
