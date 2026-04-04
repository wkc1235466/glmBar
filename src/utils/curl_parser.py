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
    return result
