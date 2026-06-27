use crate::providers::models::*;
use crate::providers::Provider;
use regex::Regex;
use std::collections::HashMap;
use std::future::Future;
use std::pin::Pin;
use std::time::Duration;

/// OpenCode Go subscription: scrape the workspace dashboard (HTML) and report
/// rolling (~5h) / weekly / monthly usage as USD-denominated windows.
///
/// Auth model mirrors Baidu Qianfan: the user pastes a curl of the dashboard
/// page; we extract the `auth` cookie and workspace id from it. Unlike Baidu,
/// the dashboard returns HTML (SolidJS SSR hydration output) rather than JSON,
/// so usage is parsed with regex. Reference: slkiser/opencode-quota.
pub struct OpencodeGoProvider {
    client: reqwest::Client,
    extra: HashMap<String, String>,
}

impl OpencodeGoProvider {
    pub fn new(client: reqwest::Client, extra: &HashMap<String, String>) -> Self {
        // opencode.ai 是纯 IPv6 的海外站点，国内直连必然超时，必须走代理。
        // 使用独立 client：更长超时 + 显式应用本机代理（自动探测系统代理，
        // 零配置）。国内 provider（如 baidu）继续用共享的全局 client 直连。
        let mut builder = reqwest::Client::builder().timeout(Duration::from_secs(30));

        if let Some(proxy_url) = detect_proxy() {
            if let Ok(proxy) = reqwest::Proxy::all(&proxy_url) {
                builder = builder.proxy(proxy);
            }
        }

        let client = builder.build().unwrap_or(client);
        Self {
            client,
            extra: extra.clone(),
        }
    }

    /// Resolve the workspace id from explicit config or the curl URL path.
    fn workspace_id(&self) -> Option<String> {
        if let Some(id) = self.extra.get("workspace_id") {
            if !id.is_empty() {
                return Some(id.clone());
            }
        }
        let url = self.extra.get("url")?;
        let re = Regex::new(r"/workspace/([^/]+)").unwrap();
        re.captures(url).map(|c| c[1].to_string())
    }

    /// Resolve the `auth` cookie value from explicit config or the cookie string.
    fn auth(&self) -> Option<String> {
        if let Some(a) = self.extra.get("auth") {
            if !a.is_empty() {
                return Some(a.clone());
            }
        }
        let cookie = self.extra.get("cookie")?;
        let re = Regex::new(r"(?:^|;)\s*auth=([^;]+)").unwrap();
        re.captures(cookie)
            .map(|c| c[1].trim().to_string())
            .filter(|s| !s.is_empty())
    }
}

impl Provider for OpencodeGoProvider {
    fn fetch_usage(&self) -> Pin<Box<dyn Future<Output = UsageData> + Send + '_>> {
        Box::pin(async move {
            let workspace_id = match self.workspace_id() {
                Some(id) => id,
                None => return UsageData::no_api_key("opencode", "OpenCode Go"),
            };
            let auth = match self.auth() {
                Some(a) => a,
                None => return UsageData::no_api_key("opencode", "OpenCode Go"),
            };

            let url = format!("https://opencode.ai/workspace/{}/go", workspace_id);

            let resp = match self
                .client
                .get(&url)
                .header("Cookie", format!("auth={}", auth))
                .header(
                    "Accept",
                    "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                )
                .header(
                    "User-Agent",
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 \
                     (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36",
                )
                .send()
                .await
            {
                Ok(r) => r,
                Err(e) => return UsageData::error("opencode", "OpenCode Go", &fmt_err(&e)),
            };

            if resp.status() == reqwest::StatusCode::UNAUTHORIZED
                || resp.status() == reqwest::StatusCode::FORBIDDEN
            {
                return UsageData::unauthorized(
                    "opencode",
                    "OpenCode Go",
                    "Cookie 已失效，请重新登录 opencode.ai 并复制新的 curl 命令",
                );
            }

            let html = match resp.text().await {
                Ok(t) => t,
                Err(e) => return UsageData::error("opencode", "OpenCode Go", &fmt_err(&e)),
            };

            // (SSR field, label, USD limit per https://opencode.ai/docs/go/)
            let window_defs = [
                ("rollingUsage", "5小时配额", 12.0),
                ("weeklyUsage", "每周配额", 30.0),
                ("monthlyUsage", "每月配额", 60.0),
            ];

            let mut windows: Vec<UsageWindow> = Vec::new();
            for (field, label, limit) in window_defs {
                if let Some((usage_percent, reset_in_sec)) = parse_ssr_window(&html, field) {
                    let pct = usage_percent.clamp(0.0, 100.0);
                    let used = pct / 100.0 * limit;
                    windows.push(UsageWindow {
                        label: label.into(),
                        used_percent: pct,
                        used,
                        total: limit,
                        remaining: (limit - used).max(0.0),
                        resets_at: Some(format_reset_iso(reset_in_sec)),
                        unit: "$".into(),
                    });
                }
            }

            if windows.is_empty() {
                return UsageData::error(
                    "opencode",
                    "OpenCode Go",
                    "无法解析用量数据，dashboard 格式可能已变更",
                );
            }

            UsageData {
                provider_id: "opencode".into(),
                provider_name: "OpenCode Go".into(),
                status: ProviderStatus::Ok,
                plan_name: "OpenCode Go".into(),
                windows,
                balance: None,
                error_message: String::new(),
                updated_at: UsageData::now_timestamp(),
            }
        })
    }
}

/// Parse a SolidJS SSR window object, e.g.
/// `rollingUsage:$R[3]={...usagePercent:42.5...resetInSec:1234...}`.
///
/// Field order varies, so both orderings are tried. Returns (usagePercent, resetInSec).
fn parse_ssr_window(html: &str, field: &str) -> Option<(f64, f64)> {
    let num = r"(-?\d+(?:\.\d+)?)";

    // Order 1: usagePercent first, then resetInSec
    let p1 = format!(
        r"{field}:\$R\[\d+\]=\{{[^}}]*usagePercent:{num}[^}}]*resetInSec:{num}[^}}]*\}}"
    );
    if let Ok(re) = Regex::new(&p1) {
        if let Some(c) = re.captures(html) {
            let pct: f64 = c[1].parse().ok()?;
            let reset: f64 = c[2].parse().ok()?;
            return Some((pct, reset));
        }
    }

    // Order 2: resetInSec first, then usagePercent
    let p2 = format!(
        r"{field}:\$R\[\d+\]=\{{[^}}]*resetInSec:{num}[^}}]*usagePercent:{num}[^}}]*\}}"
    );
    if let Ok(re) = Regex::new(&p2) {
        if let Some(c) = re.captures(html) {
            let reset: f64 = c[1].parse().ok()?;
            let pct: f64 = c[2].parse().ok()?;
            return Some((pct, reset));
        }
    }

    None
}

/// ISO 8601 timestamp `now + reset_in_sec`, parseable by the popup's `new Date()`.
fn format_reset_iso(reset_in_sec: f64) -> String {
    let secs = reset_in_sec.max(0.0) as i64;
    chrono::Local::now()
        .checked_add_signed(chrono::Duration::seconds(secs))
        .map(|t| t.to_rfc3339())
        .unwrap_or_default()
}

/// Format a reqwest error with its full cause chain for diagnostics.
fn fmt_err(e: &reqwest::Error) -> String {
    let mut msg = e.to_string();
    let mut src = std::error::Error::source(e);
    while let Some(s) = src {
        msg.push_str("\n  → ");
        msg.push_str(&s.to_string());
        src = s.source();
    }
    msg
}

/// Detect a usable proxy URL for overseas providers (e.g. opencode.ai).
/// Priority: 1) env vars HTTPS_PROXY/ALL_PROXY/HTTP_PROXY;
/// 2) Windows system proxy (registry, written by Clash/V2Ray "system proxy" mode).
fn detect_proxy() -> Option<String> {
    for var in [
        "HTTPS_PROXY",
        "https_proxy",
        "ALL_PROXY",
        "all_proxy",
        "HTTP_PROXY",
        "http_proxy",
    ] {
        if let Ok(p) = std::env::var(var) {
            if !p.is_empty() {
                return Some(p);
            }
        }
    }
    #[cfg(windows)]
    {
        if let Some(url) = read_windows_system_proxy() {
            return Some(url);
        }
    }
    None
}

/// Read the Windows registry system proxy (Internet Settings).
/// Returns `http://host:port` when a system proxy is enabled, else None.
#[cfg(windows)]
fn read_windows_system_proxy() -> Option<String> {
    use std::process::Command;
    const KEY: &str = r"HKCU\Software\Microsoft\Windows\CurrentVersion\Internet Settings";

    // ProxyEnable == 0x1 ?
    let enable = Command::new("reg")
        .args(["query", KEY, "/v", "ProxyEnable"])
        .output()
        .ok()?;
    let enable_on = String::from_utf8_lossy(&enable.stdout)
        .lines()
        .any(|l| l.contains("ProxyEnable") && l.contains("0x1"));
    if !enable_on {
        return None;
    }

    // ProxyServer, e.g. "    ProxyServer    REG_SZ    127.0.0.1:7897"
    let server_out = Command::new("reg")
        .args(["query", KEY, "/v", "ProxyServer"])
        .output()
        .ok()?;
    let server_text = String::from_utf8_lossy(&server_out.stdout);
    let server = server_text
        .lines()
        .find(|l| l.contains("ProxyServer") && l.contains("REG_SZ"))?
        .split_whitespace()
        .last()?
        .trim();
    if server.is_empty() {
        return None;
    }

    // Registry value usually lacks a scheme; reqwest needs one.
    if server.contains("://") {
        Some(server.to_string())
    } else {
        Some(format!("http://{}", server))
    }
}
