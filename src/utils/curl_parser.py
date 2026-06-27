"""curl command parser for extracting auth-related fields."""

from __future__ import annotations

import re


def parse_curl(curl_text: str) -> dict[str, str]:
    """Parse a curl command and extract auth-related fields.

    Handles both bash (``'...'`` / ``"..."``) and Windows cmd (``^"...^"``)
    quoting, since "Copy as cURL" on Windows exports the cmd format.

    Returns any of: cookie, csrftoken, x-bce-jt (Baidu Qianfan),
    url, auth (OpenCode Go).
    """
    result: dict[str, str] = {}
    # Normalize Windows cmd quoting (^" -> ") so the bash-style regexes below
    # also match cURL exported from cmd. Bash cURL never contains ^", so this
    # is a safe no-op for bash input.
    text = curl_text.replace('^"', '"')

    # Match -H 'Key: Value' or -H "Key: Value"
    headers = re.findall(r"-H\s+['\"](.+?):\s*(.+?)['\"]", text)
    for key, value in headers:
        key_lower = key.lower().strip()
        if key_lower == "cookie":
            result["cookie"] = value.strip()
        elif key_lower == "csrftoken":
            result["csrftoken"] = value.strip()
        elif key_lower == "x-bce-jt":
            result["x-bce-jt"] = value.strip()

    # Also parse -b / --cookie flags (browser "Copy as cURL" uses this format)
    if "cookie" not in result:
        m = re.search(r"(?:-b|--cookie)\s+'([^']+)'", text)
        if not m:
            m = re.search(r'(?:-b|--cookie)\s+"([^"]+)"', text)
        if m and m.group(1).strip():
            result["cookie"] = m.group(1).strip()

    # Request URL — OpenCode Go derives its workspace id from /workspace/{id}/go
    if "url" not in result:
        m = re.search(r"https?://[^\s'\"^]+", text)
        if m and m.group(0).strip():
            result["url"] = m.group(0).strip()

    # `auth` cookie value — OpenCode Go session token
    if "auth" not in result:
        cookie = result.get("cookie", "")
        m = re.search(r"(?:^|;)\s*auth=([^;]+)", cookie)
        if m and m.group(1).strip():
            result["auth"] = m.group(1).strip()

    return result
