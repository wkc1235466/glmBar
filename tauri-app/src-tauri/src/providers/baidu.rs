use crate::providers::models::*;
use crate::providers::Provider;
use std::collections::HashMap;
use std::future::Future;
use std::pin::Pin;

pub struct BaiduQianfanProvider {
    client: reqwest::Client,
    extra: HashMap<String, String>,
}

impl BaiduQianfanProvider {
    pub fn new(client: reqwest::Client, extra: &HashMap<String, String>) -> Self {
        Self {
            client,
            extra: extra.clone(),
        }
    }

    fn get_cookie(&self) -> Option<&str> {
        self.extra.get("cookie").map(|s| s.as_str()).filter(|s| !s.is_empty())
    }
}

impl Provider for BaiduQianfanProvider {
    fn fetch_usage(&self) -> Pin<Box<dyn Future<Output = UsageData> + Send + '_>> {
        Box::pin(async move {
        let cookie = match self.get_cookie() {
            Some(c) => c,
            None => {
                return UsageData::no_api_key("baidu", "百度千帆");
            }
        };

        let url = "https://console.bce.baidu.com/api/qianfan/charge/codingPlan/resourceList";

        let mut req = self.client
            .get(url)
            .header("Cookie", cookie)
            .header("Accept", "application/json;charset=UTF-8")
            .header("Content-Type", "application/json")
            .header("Referer", "https://console.bce.baidu.com/qianfan/resource/subscribe")
            .header("x-requested-with", "XMLHttpRequest")
            .timeout(std::time::Duration::from_secs(15));

        if let Some(csrf) = self.extra.get("csrftoken") {
            req = req.header("csrftoken", csrf);
        }
        if let Some(jt) = self.extra.get("x-bce-jt") {
            req = req.header("x-bce-jt", jt);
        }

        let resp = match req.send().await {
            Ok(r) => r,
            Err(e) => return UsageData::error("baidu", "百度千帆", &e.to_string()),
        };

        if resp.status() == reqwest::StatusCode::UNAUTHORIZED
            || resp.status() == reqwest::StatusCode::FORBIDDEN
        {
            return UsageData::unauthorized("baidu", "百度千帆", "Cookie 已失效，请重新登录百度智能云");
        }

        let data: serde_json::Value = match resp.json().await {
            Ok(d) => d,
            Err(e) => return UsageData::error("baidu", "百度千帆", &e.to_string()),
        };

        // Check for login redirect
        if data.get("success").and_then(|v| v.as_bool()) == Some(false) {
            if let Some(msg) = data.get("message").and_then(|v| v.as_object()) {
                if msg.get("redirect").is_some() {
                    return UsageData::unauthorized(
                        "baidu",
                        "百度千帆",
                        "Cookie 已失效，请重新登录百度智能云",
                    );
                }
            }
        }

        // Parse response
        if data.get("success").and_then(|v| v.as_bool()) != Some(true) {
            let msg = data
                .get("message")
                .and_then(|v| v.as_str())
                .unwrap_or("请求失败");
            return UsageData::error("baidu", "百度千帆", msg);
        }

        let items = data
            .get("result")
            .and_then(|r| r.get("items"))
            .and_then(|v| v.as_array())
            .cloned()
            .unwrap_or_default();

        if items.is_empty() {
            return UsageData::error("baidu", "百度千帆", "未找到用量数据");
        }

        let item = &items[0];
        let plan_name = item
            .get("planType")
            .and_then(|v| v.as_str())
            .unwrap_or("")
            .to_string();

        let quota = item.get("quota").cloned().unwrap_or(serde_json::json!({}));
        let mut windows: Vec<UsageWindow> = Vec::new();

        let window_defs = vec![
            ("fiveHour", "5小时配额"),
            ("week", "每周配额"),
            ("month", "每月配额"),
        ];

        for (key, label) in window_defs {
            let entry = match quota.get(key) {
                Some(e) => e,
                None => continue,
            };

            let used = entry.get("used").and_then(|v| v.as_f64()).unwrap_or(0.0);
            let limit = entry.get("limit").and_then(|v| v.as_f64()).unwrap_or(0.0);
            if limit <= 0.0 {
                continue;
            }

            let resets_at = entry
                .get("resetAt")
                .and_then(|v| v.as_str())
                .map(|s| s.to_string());

            windows.push(UsageWindow {
                label: label.into(),
                used_percent: ((used / limit) * 100.0).min(100.0),
                used,
                total: limit,
                remaining: limit - used,
                resets_at,
                unit: "次".into(),
            });
        }

        let is_empty = windows.is_empty();
        UsageData {
            provider_id: "baidu".into(),
            provider_name: "百度千帆".into(),
            status: if is_empty {
                ProviderStatus::Error
            } else {
                ProviderStatus::Ok
            },
            plan_name,
            windows,
            balance: None,
            error_message: if is_empty {
                "无法解析用量数据".into()
            } else {
                String::new()
            },
            updated_at: UsageData::now_timestamp(),
        }
        })
    }
}
