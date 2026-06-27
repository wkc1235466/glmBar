use regex::Regex;
use std::collections::HashMap;

/// Parse a curl command and extract auth-related fields.
///
/// Handles both bash (`'...'` / `"..."`) and Windows cmd (`^"..."`) quoting,
/// since "Copy as cURL" on Windows exports the cmd format.
///
/// Extracted keys:
/// - `cookie`, `csrftoken`, `x-bce-jt` — Baidu Qianfan auth headers.
/// - `url` — the request URL (used to derive the OpenCode Go workspace id).
/// - `auth` — the `auth` cookie value (OpenCode Go session token).
pub fn parse_curl(curl_text: &str) -> HashMap<String, String> {
    let mut result: HashMap<String, String> = HashMap::new();

    // Normalize Windows cmd quoting (`^"` -> `"`) so the bash-style regexes
    // below also match cURL exported from cmd. Bash cURL never contains `^"`,
    // so this is a safe no-op for bash input.
    let text = curl_text.replace("^\"", "\"");

    // Single-quoted headers: -H 'Key: Value' or --header 'Key: Value'
    // Use [^'] so nested double quotes in values are preserved correctly
    let re_sq = Regex::new(r#"(?:-H|--header)\s+'([^']+?):\s*([^']*)'"#).unwrap();

    // Double-quoted headers: -H "Key: Value" or --header "Key: Value"
    // Use [^"] so nested single quotes in values are preserved correctly
    let re_dq = Regex::new(r#"(?:-H|--header)\s+"([^"]+?):\s*([^"]*)""#).unwrap();

    for re in &[re_sq, re_dq] {
        for cap in re.captures_iter(&text) {
            let key = cap[1].trim().to_lowercase();
            let value = cap[2].trim().to_string();
            if value.is_empty() {
                continue;
            }
            match key.as_str() {
                "cookie" => {
                    result.insert("cookie".into(), value);
                }
                "csrftoken" => {
                    result.insert("csrftoken".into(), value);
                }
                "x-bce-jt" => {
                    result.insert("x-bce-jt".into(), value);
                }
                _ => {}
            }
        }
    }

    // Also parse -b / --cookie flags: -b 'cookie_string' or --cookie "cookie_string"
    // This is how browsers export curl commands for Baidu Qianfan / OpenCode Go
    let re_cookie_sq = Regex::new(r#"(?:-b|--cookie)\s+'([^']+)'"#).unwrap();
    let re_cookie_dq = Regex::new(r#"(?:-b|--cookie)\s+"([^"]+)""#).unwrap();

    if !result.contains_key("cookie") {
        for re in &[re_cookie_sq, re_cookie_dq] {
            if let Some(cap) = re.captures(&text) {
                let value = cap[1].trim().to_string();
                if !value.is_empty() {
                    result.insert("cookie".into(), value);
                    break;
                }
            }
        }
    }

    // Extract the request URL (first http(s) URL). OpenCode Go derives its
    // workspace id from the `/workspace/{id}/go` path.
    if !result.contains_key("url") {
        let re_url = Regex::new(r#"https?://[^\s'"^]+"#).unwrap();
        if let Some(m) = re_url.find(&text) {
            let url = m.as_str().to_string();
            if !url.is_empty() {
                result.insert("url".into(), url);
            }
        }
    }

    // Extract the `auth` cookie value (OpenCode Go session token).
    if !result.contains_key("auth") {
        if let Some(cookie) = result.get("cookie") {
            let re_auth = Regex::new(r"(?:^|;)\s*auth=([^;]+)").unwrap();
            if let Some(cap) = re_auth.captures(cookie) {
                let value = cap[1].trim().to_string();
                if !value.is_empty() {
                    result.insert("auth".into(), value);
                }
            }
        }
    }

    result
}
