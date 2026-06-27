"""OpenCode Go provider - Cookie-authenticated dashboard scraper.

Mirrors the Tauri ``opencode.rs`` implementation. The OpenCode Go workspace
dashboard returns HTML (SolidJS SSR hydration output) rather than JSON, so
usage is parsed with regex. Reference: slkiser/opencode-quota.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

import httpx

from .base import BaseProvider, ProviderStatus, UsageData, UsageWindow

# (SSR field, label, USD limit) per https://opencode.ai/docs/go/
_WINDOW_DEFS: list[tuple[str, str, float]] = [
    ("rollingUsage", "5小时配额", 12.0),
    ("weeklyUsage", "每周配额", 30.0),
    ("monthlyUsage", "每月配额", 60.0),
]


class OpencodeGoProvider(BaseProvider):
    """OpenCode Go 套餐用量 Provider（Cookie 认证，dashboard 抓取）。

    用户通过在浏览器中复制 workspace/go 页面的 curl 命令来配置认证信息。
    """

    DASHBOARD_URL = "https://opencode.ai/workspace/{workspace_id}/go"
    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36"
    )

    def __init__(self, api_key: str = "", **kwargs):
        super().__init__(
            provider_id="opencode",
            name="OpenCode Go",
            description="OpenCode Go 套餐用量",
            requires_api_key=False,
            api_key=api_key,
            **kwargs,
        )

    def get_api_key(self) -> str | None:
        return None

    def _get_workspace_id(self) -> str | None:
        wid = self.extra_config.get("workspace_id", "")
        if wid:
            return wid
        url = self.extra_config.get("url", "")
        m = re.search(r"/workspace/([^/]+)", url)
        return m.group(1) if m else None

    def _get_auth(self) -> str | None:
        auth = self.extra_config.get("auth", "")
        if auth:
            return auth
        cookie = self.extra_config.get("cookie", "")
        m = re.search(r"(?:^|;)\s*auth=([^;]+)", cookie)
        return m.group(1).strip() if m else None

    async def fetch_usage(self) -> UsageData:
        workspace_id = self._get_workspace_id()
        auth = self._get_auth()
        if not workspace_id or not auth:
            return UsageData(
                provider_id=self.provider_id,
                provider_name=self.name,
                status=ProviderStatus.NO_API_KEY,
                error_message="请先在设置中粘贴 curl 命令",
            )

        url = self.DASHBOARD_URL.format(workspace_id=workspace_id)
        headers = {
            "Cookie": f"auth={auth}",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "User-Agent": self.USER_AGENT,
        }

        try:
            # trust_env=True (default): honor system/HTTP_PROXY so opencode.ai
            # (overseas) can be reached through a proxy. Baidu stays trust_env=False.
            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.get(url, headers=headers, follow_redirects=True)
                if resp.status_code in (401, 403):
                    return UsageData(
                        provider_id=self.provider_id,
                        provider_name=self.name,
                        status=ProviderStatus.UNAUTHORIZED,
                        error_message="Cookie 已失效，请重新登录 opencode.ai 并复制新的 curl 命令",
                    )
                resp.raise_for_status()
                html = resp.text
        except httpx.HTTPError as e:
            return UsageData(
                provider_id=self.provider_id,
                provider_name=self.name,
                status=ProviderStatus.ERROR,
                error_message=str(e),
            )

        windows: list[UsageWindow] = []
        for field, label, limit in _WINDOW_DEFS:
            parsed = _parse_ssr_window(html, field)
            if parsed is None:
                continue
            usage_percent, reset_in_sec = parsed
            pct = max(0.0, min(usage_percent, 100.0))
            used = pct / 100.0 * limit
            windows.append(
                UsageWindow(
                    label=label,
                    used_percent=pct,
                    used=used,
                    total=limit,
                    remaining=max(limit - used, 0.0),
                    resets_at=datetime.now(timezone.utc) + timedelta(seconds=max(reset_in_sec, 0)),
                    unit="$",
                )
            )

        if not windows:
            return UsageData(
                provider_id=self.provider_id,
                provider_name=self.name,
                status=ProviderStatus.ERROR,
                error_message="无法解析用量数据，dashboard 格式可能已变更",
            )

        return UsageData(
            provider_id=self.provider_id,
            provider_name=self.name,
            status=ProviderStatus.OK,
            plan_name="OpenCode Go",
            windows=windows,
        )

    def get_display_config(self) -> dict[str, str]:
        return {"curl": "textarea"}

    @classmethod
    def parse_curl(cls, curl_text: str) -> dict[str, str]:
        """解析 curl 命令文本，返回提取的认证字段。"""
        from src.utils.curl_parser import parse_curl

        return parse_curl(curl_text)


def _parse_ssr_window(html: str, field: str) -> tuple[float, float] | None:
    """Parse a SolidJS SSR window object, e.g.
    ``rollingUsage:$R[3]={...usagePercent:42.5...resetInSec:1234...}``.

    Field order varies; both orderings are tried.
    Returns (usagePercent, resetInSec) or None.
    """
    num = r"(-?\d+(?:\.\d+)?)"
    # Order 1: usagePercent first, then resetInSec
    m = re.search(
        rf"{field}:\$R\[\d+\]=\{{[^}}]*usagePercent:{num}[^}}]*resetInSec:{num}[^}}]*\}}",
        html,
    )
    if m:
        return float(m.group(1)), float(m.group(2))
    # Order 2: resetInSec first, then usagePercent
    m = re.search(
        rf"{field}:\$R\[\d+\]=\{{[^}}]*resetInSec:{num}[^}}]*usagePercent:{num}[^}}]*\}}",
        html,
    )
    if m:
        return float(m.group(2)), float(m.group(1))
    return None
