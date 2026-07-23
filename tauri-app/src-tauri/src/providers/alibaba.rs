use crate::providers::models::*;
use crate::providers::Provider;
use std::future::Future;
use std::pin::Pin;

pub struct AlibabaProvider {
    client: reqwest::Client,
    api_key: String,
    region: String,
}

impl AlibabaProvider {
    pub fn new(client: reqwest::Client, api_key: &str, region: Option<&str>) -> Self {
        Self {
            client,
            api_key: api_key.to_string(),
            region: region.unwrap_or("china").to_string(),
        }
    }

    fn base_url(&self) -> String {
        match self.region.as_str() {
            "china" => "https://bailian.console.aliyun.com".to_string(),
            "global" => "https://modelstudio.console.alibabacloud.com".to_string(),
            other if other.starts_with("http") => other.to_string(),
            other => format!("https://{}", other),
        }
    }

    fn fallback_url(&self) -> String {
        match self.region.as_str() {
            "china" => "https://modelstudio.console.alibabacloud.com".to_string(),
            _ => "https://bailian.console.aliyun.com".to_string(),
        }
    }

    fn build_url(host: &str) -> String {
        format!(
            "{}/data/api.json?action=zeldaEasy.broadscope-bailian.codingPlan.queryCodingPlanInstanceInfoV2&product=broadscope-bailian&api=queryCodingPlanInstanceInfoV2",
            host
        )
    }

    fn parse_response(&self, data: &serde_json::Value) -> UsageData {
        let mut windows: Vec<UsageWindow> = Vec::new();

        let instances = data
            .get("codingPlanInstanceInfos")
            .or_else(|| data.get("Data").and_then(|d| d.get("codingPlanInstanceInfos")))
            .and_then(|v| v.as_array())
            .cloned()
            .unwrap_or_default();

        let mut plan_name = String::new();

        for inst in &instances {
            plan_name = inst
                .get("planName")
                .or(inst.get("instanceName"))
                .or(inst.get("packageName"))
                .and_then(|v| v.as_str())
                .unwrap_or(&plan_name)
                .to_string();

            let quota = match inst.get("codingPlanQuotaInfo") {
                Some(q) => q,
                None => continue,
            };

            // 5-hour window
            let h5_used = quota
                .get("per5HourUsedQuota")
                .and_then(|v| v.as_f64())
                .unwrap_or(0.0);
            let h5_total = quota
                .get("per5HourTotalQuota")
                .and_then(|v| v.as_f64())
                .unwrap_or(0.0);
            if h5_total > 0.0 {
                windows.push(UsageWindow {
                    label: "5小时配额".into(),
                    used_percent: ((h5_used / h5_total) * 100.0).min(100.0),
                    used: h5_used,
                    total: h5_total,
                    remaining: h5_total - h5_used,
                    resets_at: quota
                        .get("per5HourQuotaNextRefreshTime")
                        .and_then(|v| v.as_str())
                        .map(|s| s.replace('Z', "+00:00")),
                    unit: "units".into(),
                });
            }

            // Weekly window
            let wk_used = quota
                .get("perWeekUsedQuota")
                .and_then(|v| v.as_f64())
                .unwrap_or(0.0);
            let wk_total = quota
                .get("perWeekTotalQuota")
                .and_then(|v| v.as_f64())
                .unwrap_or(0.0);
            if wk_total > 0.0 {
                windows.push(UsageWindow {
                    label: "每周配额".into(),
                    used_percent: ((wk_used / wk_total) * 100.0).min(100.0),
                    used: wk_used,
                    total: wk_total,
                    remaining: wk_total - wk_used,
                    resets_at: quota
                        .get("perWeekQuotaNextRefreshTime")
                        .and_then(|v| v.as_str())
                        .map(|s| s.replace('Z', "+00:00")),
                    unit: "units".into(),
                });
            }

            // Monthly window
            let mo_used = quota
                .get("perBillMonthUsedQuota")
                .and_then(|v| v.as_f64())
                .unwrap_or(0.0);
            let mo_total = quota
                .get("perBillMonthTotalQuota")
                .and_then(|v| v.as_f64())
                .unwrap_or(0.0);
            if mo_total > 0.0 {
                windows.push(UsageWindow {
                    label: "每月配额".into(),
                    used_percent: ((mo_used / mo_total) * 100.0).min(100.0),
                    used: mo_used,
                    total: mo_total,
                    remaining: mo_total - mo_used,
                    resets_at: quota
                        .get("perBillMonthQuotaNextRefreshTime")
                        .and_then(|v| v.as_str())
                        .map(|s| s.replace('Z', "+00:00")),
                    unit: "units".into(),
                });
            }
        }

        let is_empty = windows.is_empty();
        UsageData {
            provider_id: "alibaba".into(),
            provider_name: "阿里云百炼".into(),
            status: if is_empty {
                ProviderStatus::Error
            } else {
                ProviderStatus::Ok
            },
            plan_name,
            windows,
            balance: None,
                plan_expires: None,
            error_message: if is_empty {
                "未找到配额数据".into()
            } else {
                String::new()
            },
            updated_at: UsageData::now_timestamp(),
        }
    }
}

impl Provider for AlibabaProvider {
    fn fetch_usage(&self) -> Pin<Box<dyn Future<Output = UsageData> + Send + '_>> {
        Box::pin(async move {
        if self.api_key.is_empty() {
            return UsageData::no_api_key("alibaba", "阿里云百炼");
        }

        let url = Self::build_url(&self.base_url());

        let resp = match self.client
            .post(&url)
            .header("Authorization", format!("Bearer {}", self.api_key))
            .header("x-api-key", &self.api_key)
            .header("X-DashScope-API-Key", &self.api_key)
            .header("Content-Type", "application/json")
            .header("Accept", "application/json")
            .json(&serde_json::json!({}))
            .timeout(std::time::Duration::from_secs(15))
            .send()
            .await
        {
            Ok(r) => r,
            Err(e) => return UsageData::error("alibaba", "阿里云百炼", &e.to_string()),
        };

        if resp.status() == reqwest::StatusCode::UNAUTHORIZED {
            // Try fallback region
            let fallback_url = Self::build_url(&self.fallback_url());
            let resp2 = match self.client
                .post(&fallback_url)
                .header("Authorization", format!("Bearer {}", self.api_key))
                .header("x-api-key", &self.api_key)
                .header("X-DashScope-API-Key", &self.api_key)
                .header("Content-Type", "application/json")
                .header("Accept", "application/json")
                .json(&serde_json::json!({}))
                .timeout(std::time::Duration::from_secs(15))
                .send()
                .await
            {
                Ok(r) => r,
                Err(_) => {
                    return UsageData::unauthorized("alibaba", "阿里云百炼", "API 密钥无效或已过期")
                }
            };

            let data: serde_json::Value = match resp2.json().await {
                Ok(d) => d,
                Err(e) => return UsageData::error("alibaba", "阿里云百炼", &e.to_string()),
            };

            if data
                .get("Code")
                .and_then(|v| v.as_str())
                .map(|c| c == "ConsoleNeedLogin")
                .unwrap_or(false)
            {
                return UsageData::error(
                    "alibaba",
                    "阿里云百炼",
                    "两个区域均需要控制台登录",
                );
            }
            return self.parse_response(&data);
        }

        let data: serde_json::Value = match resp.json().await {
            Ok(d) => d,
            Err(e) => return UsageData::error("alibaba", "阿里云百炼", &e.to_string()),
        };

        if data
            .get("Code")
            .and_then(|v| v.as_str())
            .map(|c| c == "ConsoleNeedLogin")
            .unwrap_or(false)
        {
            return UsageData::error(
                "alibaba",
                "阿里云百炼",
                "需要控制台登录 - 此账号不支持 API 密钥模式",
            );
        }

        self.parse_response(&data)
        })
    }
}
