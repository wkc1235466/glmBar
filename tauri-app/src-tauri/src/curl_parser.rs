use regex::Regex;
use std::collections::HashMap;

/// Parse a curl command and extract Baidu Qianfan auth headers.
pub fn parse_curl(curl_text: &str) -> HashMap<String, String> {
    let mut result: HashMap<String, String> = HashMap::new();

    // Match -H 'Key: Value' or -H "Key: Value"
    let re = Regex::new(r#"-H\s+['"](.+?):\s*(.+?)['"]"#).unwrap();

    for cap in re.captures_iter(curl_text) {
        let key = cap[1].to_lowercase();
        let value = cap[2].trim().to_string();

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

    result
}
