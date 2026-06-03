"""curl command parser for extracting HTTP headers."""

from __future__ import annotations

import re


def parse_curl(curl_text: str) -> dict[str, str]:
    """Parse a curl command and extract Baidu Qianfan auth headers.

    Returns a dict with any of: cookie, csrftoken, x-bce-jt.
    """
    result: dict[str, str] = {}
    # Match -H 'Key: Value' or -H "Key: Value"
    headers = re.findall(r"-H\s+['\"](.+?):\s*(.+?)['\"]", curl_text)
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
        m = re.search(r"(?:-b|--cookie)\s+'([^']+)'", curl_text)
        if not m:
            m = re.search(r'(?:-b|--cookie)\s+"([^"]+)"', curl_text)
        if m and m.group(1).strip():
            result["cookie"] = m.group(1).strip()

    return result
