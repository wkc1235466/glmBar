"""Ollama provider - Cookie-based authentication, HTML scraping."""

from __future__ import annotations

import re
from datetime import datetime, timezone

import httpx

from .base import BaseProvider, ProviderStatus, UsageData, UsageWindow


class OllamaProvider(BaseProvider):
    """Ollama 用量 Provider（Cookie 认证）。

    用户通过在浏览器中复制 curl 命令来配置认证信息。
    用量数据从 https://ollama.com/settings 页面 HTML 中解析。
    到期日期从 https://ollama.com/settings/billing 页面中解析。
    """

    SETTINGS_URL = "https://ollama.com/settings"
    BILLING_URL = "https://ollama.com/settings/billing"
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
                # Fetch settings page for usage data
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

                # Fetch billing page for expiration date
                plan_expires = None
                try:
                    resp_billing = await client.get(
                        self.BILLING_URL, headers=headers, follow_redirects=True
                    )
                    if resp_billing.status_code not in (401, 403):
                        resp_billing.raise_for_status()
                        plan_expires = _parse_expires_date(resp_billing.text)
                except httpx.HTTPError:
                    pass  # Non-critical: expiration date is optional
        except httpx.HTTPError as e:
            return UsageData(
                provider_id=self.provider_id,
                provider_name=self.name,
                status=ProviderStatus.ERROR,
                error_message=str(e),
            )

        return self._parse_html(html, plan_expires)

    def _parse_html(self, html: str, plan_expires: str | None = None) -> UsageData:
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

        if not windows:
            return UsageData(
                provider_id=self.provider_id,
                provider_name=self.name,
                status=ProviderStatus.ERROR,
                error_message="无法解析用量数据，页面格式可能已变更",
            )

        return UsageData(
            provider_id=self.provider_id,
            provider_name=self.name,
            status=ProviderStatus.OK,
            plan_name="Ollama Pro",
            windows=windows,
            plan_expires=plan_expires,
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
    pattern = re.escape(section) + r"[\s\S]*?(\d+(?:\.\d+)?)% used"
    m = re.search(pattern, html)
    if m:
        return max(0.0, min(float(m.group(1)), 100.0))
    return None


def _parse_reset_time(html: str, section: str) -> datetime | None:
    """Parse the reset time after a section label.

    The HTML structure is:
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


# Month name → number mapping for English date parsing
_MONTH_MAP = {
    "january": "01", "february": "02", "march": "03", "april": "04",
    "may": "05", "june": "06", "july": "07", "august": "08",
    "september": "09", "october": "10", "november": "11", "december": "12",
}


def _parse_expires_date(html: str) -> str | None:
    """Parse the Pro plan expiration date from the billing page HTML.

    Looks for English date formats like "August 23, 2026" or "Aug 23, 2026"
    and returns an ISO date string "2026-08-23".
    """
    # Pattern: "Month DD, YYYY" or "Mon DD, YYYY"
    m = re.search(
        r"(January|February|March|April|May|June|July|August|September|October|November|December"
        r"|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
        r"\s+(\d{1,2}),?\s+(\d{4})",
        html,
        re.IGNORECASE,
    )
    if m:
        month_str = _MONTH_MAP.get(m.group(1).lower())
        if month_str:
            day = int(m.group(2))
            year = m.group(3)
            return f"{year}-{month_str}-{day:02d}"
    return None