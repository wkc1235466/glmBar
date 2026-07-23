use crate::providers::models::*;
use crate::providers::Provider;
use regex::Regex;
use std::collections::HashMap;
use std::future::Future;
use std::pin::Pin;

/// Ollama Pro subscription: scrape the settings page (HTML) and report
/// session / weekly usage as percentage-based windows plus extra-usage balance.
///
/// Auth model mirrors Baidu Qianfan / OpenCode Go: the user pastes a curl of
/// the settings page; we extract the cookie from it and fetch the HTML.
pub struct OllamaProvider {
    client: reqwest::Client,
    extra: HashMap<String, String>,
}

impl OllamaProvider {
    pub fn new(client: reqwest::Client, extra: &HashMap<String, String>) -> Self {
        Self {
            client,
            extra: extra.clone(),
        }
    }

    fn get_cookie(&self) -> Option<&str> {
        self.extra
            .get("cookie")
            .map(|s| s.as_str())
            .filter(|s| !s.is_empty())
    }
}

impl Provider for OllamaProvider {
    fn fetch_usage(&self) -> Pin<Box<dyn Future<Output = UsageData> + Send + '_>> {
        Box::pin(async move {
            let cookie = match self.get_cookie() {
                Some(c) => c,
                None => {
                    return UsageData::no_api_key("ollama", "Ollama");
                }
            };

            let url = "https://ollama.com/settings";

            let resp = match self
                .client
                .get(url)
                .header("Cookie", cookie)
                .header(
                    "Accept",
                    "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                )
                .header(
                    "User-Agent",
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 \
                     (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36",
                )
                .timeout(std::time::Duration::from_secs(20))
                .send()
                .await
            {
                Ok(r) => r,
                Err(e) => return UsageData::error("ollama", "Ollama", &e.to_string()),
            };

            if resp.status() == reqwest::StatusCode::UNAUTHORIZED
                || resp.status() == reqwest::StatusCode::FORBIDDEN
            {
                return UsageData::unauthorized(
                    "ollama",
                    "Ollama",
                    "Cookie 已失效，请重新登录 ollama.com 并复制新的 curl 命令",
                );
            }

            let html = match resp.text().await {
                Ok(t) => t,
                Err(e) => return UsageData::error("ollama", "Ollama", &e.to_string()),
            };

            let mut windows: Vec<UsageWindow> = Vec::new();

            // Session usage
            if let Some(pct) = parse_usage_percent(&html, "Session usage") {
                let reset = parse_reset_time(&html, "Session usage");
                windows.push(UsageWindow {
                    label: "Session".into(),
                    used_percent: pct,
                    used: pct,
                    total: 100.0,
                    remaining: 100.0 - pct,
                    resets_at: reset,
                    unit: "%".into(),
                });
            }

            // Weekly usage
            if let Some(pct) = parse_usage_percent(&html, "Weekly usage") {
                let reset = parse_reset_time(&html, "Weekly usage");
                windows.push(UsageWindow {
                    label: "每周".into(),
                    used_percent: pct,
                    used: pct,
                    total: 100.0,
                    remaining: 100.0 - pct,
                    resets_at: reset,
                    unit: "%".into(),
                });
            }

            if windows.is_empty() {
                return UsageData::error(
                    "ollama",
                    "Ollama",
                    "无法解析用量数据，页面格式可能已变更",
                );
            }

            UsageData {
                provider_id: "ollama".into(),
                provider_name: "Ollama".into(),
                status: ProviderStatus::Ok,
                plan_name: "Ollama Pro".into(),
                windows,
                balance: None,
                error_message: String::new(),
                updated_at: UsageData::now_timestamp(),
            }
        })
    }
}

/// Parse usage percentage after a section label like "Session usage" or "Weekly usage".
/// Looks for: `<span>Section usage</span> ... <span class="text-sm ">X.X% used</span>`
fn parse_usage_percent(html: &str, section: &str) -> Option<f64> {
    let pattern = format!(
        r"{section}[\s\S]*?(\d+(?:\.\d+)?)% used"
    );
    let re = Regex::new(&pattern).ok()?;
    let cap = re.captures(html)?;
    let pct: f64 = cap[1].parse().ok()?;
    Some(pct.clamp(0.0, 100.0))
}

/// Parse the reset time after a section label.
/// Looks for: `<div class="... local-time" data-time="2026-07-23T12:00:00Z">`
fn parse_reset_time(html: &str, section: &str) -> Option<String> {
    let pattern = format!(
        r#"{section}[\s\S]*?data-time="(\d{{4}}-\d{{2}}-\d{{2}}T\d{{2}}:\d{{2}}:\d{{2}}Z)""#
    );
    let re = Regex::new(&pattern).ok()?;
    let cap = re.captures(html)?;
    Some(cap[1].to_string().replace('Z', "+00:00"))
}

