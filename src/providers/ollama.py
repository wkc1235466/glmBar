"""Ollama provider - Cookie-based authentication, HTML scraping."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

import httpx

from .base import BaseProvider, ProviderStatus, UsageData, UsageWindow


class OllamaProvider(BaseProvider):
    """Ollama 用量 Provider（Cookie 认证）。

    用户通过在浏览器中复制 curl 命令来配置认证信息。
    用量数据从 https://ollama.com/settings 页面 HTML 中解析。
    """

    SETTINGS_URL = "https://ollama.com/settings"
    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36"
    )

    def __init__(self, api_key: str = "", **kwargs):
        super().__init__(
            provider_id="ollama",
            name="Ollama",
            description="Ollama Pro 套餐用量",
            requires_api_key=False,
            api_key=api_key,
            **kwargs,
        )

    def get_api_key(self) -> str | None:
        return None

    def _get_cookie(self) -> str | None:
        cookie = self.extra_config.get("cookie", "")
        return cookie if cookie else None

    async def fetch_usage(self) -> UsageData:
        cookie = self._get_cookie()
        if not cookie:
            return UsageData(
                provider_id=self.provider_id,
                provider_name=self.name,
                status=ProviderStatus.NO_API_KEY,
                error_message="请先在设置中粘贴 curl 命令",
            )

        headers = {
            "Cookie": cookie,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "User-Agent": self.USER_AGENT,
        }

        try:
            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.get(
                    self.SETTINGS_URL, headers=headers, follow_redirects=True
                )
                if resp.status_code in (401, 403):
                    return UsageData(
                        provider_id=self.provider_id,
                        provider_name=self.name,
                        status=ProviderStatus.UNAUTHORIZED,
                        error_message="Cookie 已失效，请重新登录 ollama.com 并复制新的 curl 命令",
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

        return self._parse_html(html)

    def _parse_html(self, html: str) -> UsageData:
        windows: list[UsageWindow] = []

        # Parse session usage: "Session usage" ... "X.X% used"
        session_pct = _parse_usage_percent(html, "Session usage")
        session_reset = _parse_reset_time(html, "Session usage")
        if session_pct is not None:
            windows.append(
                UsageWindow(
                    label="Session",
                    used_percent=session_pct,
                    used=session_pct,
                    total=100.0,
                    remaining=100.0 - session_pct,
                    resets_at=session_reset,
                    unit="%",
                )
            )

        # Parse weekly usage: "Weekly usage" ... "X.X% used"
        weekly_pct = _parse_usage_percent(html, "Weekly usage")
        weekly_reset = _parse_reset_time(html, "Weekly usage")
        if weekly_pct is not None:
            windows.append(
                UsageWindow(
                    label="每周",
                    used_percent=weekly_pct,
                    used=weekly_pct,
                    total=100.0,
                    remaining=100.0 - weekly_pct,
                    resets_at=weekly_reset,
                    unit="%",
                )
            )

        return UsageData(
            provider_id=self.provider_id,
            provider_name=self.name,
            status=ProviderStatus.OK,
            plan_name="Ollama Pro",
            windows=windows,
        )

    def get_display_config(self) -> dict[str, str]:
        return {"curl": "textarea"}

    @classmethod
    def parse_curl(cls, curl_text: str) -> dict[str, str]:
        """解析 curl 命令文本，返回提取的认证字段。"""
        from src.utils.curl_parser import parse_curl

        return parse_curl(curl_text)


def _parse_usage_percent(html: str, section: str) -> float | None:
    """Parse usage percentage after a section label like 'Session usage' or 'Weekly usage'.

    The HTML structure is:
      <span>Section usage</span>
      ...
      <span class="text-sm ">X.X% used</span>
    """
    # Find the section label first, then look for the percentage in following text
    pattern = re.escape(section) + r"[\s\S]*?(\d+(?:\.\d+)?)% used"
    m = re.search(pattern, html)
    if m:
        return max(0.0, min(float(m.group(1)), 100.0))
    return None


def _parse_reset_time(html: str, section: str) -> datetime | None:
    """Parse the reset time after a section label.

    The HTML structure is:
      <span>Section usage</span>
      ...
      <div class="... local-time" data-time="2026-07-23T12:00:00Z">
    """
    pattern = re.escape(section) + r"[\s\S]*?data-time=\"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z)\""
    m = re.search(pattern, html)
    if m:
        try:
            return datetime.fromisoformat(m.group(1).replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return None
    return None


