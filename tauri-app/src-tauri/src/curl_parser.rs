use regex::Regex;
use std::collections::HashMap;

/// Parse a curl command and extract Baidu Qianfan auth headers.
pub fn parse_curl(curl_text: &str) -> HashMap<String, String> {
    let mut result: HashMap<String, String> = HashMap::new();

    // Single-quoted headers: -H 'Key: Value' or --header 'Key: Value'
    // Use [^'] so nested double quotes in values are preserved correctly
    let re_sq = Regex::new(r#"(?:-H|--header)\s+'([^']+?):\s*([^']*)'"#).unwrap();

    // Double-quoted headers: -H "Key: Value" or --header "Key: Value"
    // Use [^"] so nested single quotes in values are preserved correctly
    let re_dq = Regex::new(r#"(?:-H|--header)\s+"([^"]+?):\s*([^"]*)""#).unwrap();

    for re in &[re_sq, re_dq] {
        for cap in re.captures_iter(curl_text) {
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
    // This is how browsers export curl commands for Baidu Qianfan
    let re_cookie_sq = Regex::new(r#"(?:-b|--cookie)\s+'([^']+)'"#).unwrap();
    let re_cookie_dq = Regex::new(r#"(?:-b|--cookie)\s+"([^"]+)""#).unwrap();

    if !result.contains_key("cookie") {
        for re in &[re_cookie_sq, re_cookie_dq] {
            if let Some(cap) = re.captures(curl_text) {
                let value = cap[1].trim().to_string();
                if !value.is_empty() {
                    result.insert("cookie".into(), value);
                    break;
                }
            }
        }
    }

    result
}
