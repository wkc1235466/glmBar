"""Baidu Qianfan (百度千帆) provider - Cookie-based authentication."""

from __future__ import annotations

from datetime import datetime

import httpx

from .base import BaseProvider, ProviderStatus, UsageData, UsageWindow


class BaiduQianfanProvider(BaseProvider):
    """百度千帆编程套餐用量 Provider（Cookie 认证）。

    用户通过在浏览器中复制 curl 命令来配置认证信息。
    """

    API_URL = "https://console.bce.baidu.com/api/qianfan/charge/codingPlan/resourceList"

    def __init__(self, api_key: str = "", **kwargs):
        super().__init__(
            provider_id="baidu",
            name="百度千帆",
            description="百度千帆编程套餐用量",
            requires_api_key=False,
            api_key=api_key,
            **kwargs,
        )

    def get_api_key(self) -> str | None:
        return None

    def _get_cookie_header(self) -> str | None:
        manual = self.extra_config.get("cookie", "")
        if manual:
            return manual
        return None

    def _get_auth_headers(self) -> dict[str, str]:
        """从 extra_config 获取额外的认证请求头。"""
        headers: dict[str, str] = {}
        csrftoken = self.extra_config.get("csrftoken", "")
        if csrftoken:
            headers["csrftoken"] = csrftoken
        x_bce_jt = self.extra_config.get("x-bce-jt", "")
        if x_bce_jt:
            headers["x-bce-jt"] = x_bce_jt
        return headers

    async def fetch_usage(self) -> UsageData:
        cookie = self._get_cookie_header()
        if not cookie:
            return UsageData(
                provider_id=self.provider_id,
                provider_name=self.name,
                status=ProviderStatus.NO_API_KEY,
                error_message="请先在设置中粘贴 curl 命令",
            )

        headers = {
            "Cookie": cookie,
            "Accept": "application/json;charset=UTF-8",
            "Content-Type": "application/json",
            "Referer": "https://console.bce.baidu.com/qianfan/resource/subscribe",
            "x-requested-with": "XMLHttpRequest",
        }
        headers.update(self._get_auth_headers())

        try:
            async with httpx.AsyncClient(timeout=15, trust_env=False) as client:
                resp = await client.get(self.API_URL, headers=headers)

                if resp.status_code in (401, 403):
                    return UsageData(
                        provider_id=self.provider_id,
                        provider_name=self.name,
                        status=ProviderStatus.UNAUTHORIZED,
                        error_message="Cookie 已失效，请重新登录百度智能云",
                    )
                resp.raise_for_status()
                data = resp.json()

        except httpx.HTTPError as e:
            return UsageData(
                provider_id=self.provider_id,
                provider_name=self.name,
                status=ProviderStatus.ERROR,
                error_message=str(e),
            )

        # 检查登录重定向
        if not data.get("success") and isinstance(data.get("message"), dict):
            if data["message"].get("redirect"):
                return UsageData(
                    provider_id=self.provider_id,
                    provider_name=self.name,
                    status=ProviderStatus.UNAUTHORIZED,
                    error_message="Cookie 已失效，请重新登录百度智能云",
                    raw_response=data,
                )

        return self._parse_response(data)

    def _parse_response(self, data: dict) -> UsageData:
        if not data.get("success"):
            return UsageData(
                provider_id=self.provider_id,
                provider_name=self.name,
                status=ProviderStatus.ERROR,
                error_message=data.get("message", "请求失败") if isinstance(data.get("message"), str) else "请求失败",
                raw_response=data,
            )

        items = data.get("result", {}).get("items", [])
        if not items:
            return UsageData(
                provider_id=self.provider_id,
                provider_name=self.name,
                status=ProviderStatus.ERROR,
                error_message="未找到用量数据",
                raw_response=data,
            )

        item = items[0]
        plan_name = item.get("planType", "")
        quota = item.get("quota", {})

        windows: list[UsageWindow] = []
        window_defs = [
            ("fiveHour", "5小时配额"),
            ("week", "每周配额"),
            ("month", "每月配额"),
        ]

        for key, label in window_defs:
            entry = quota.get(key)
            if not entry:
                continue

            used = float(entry.get("used", 0))
            limit = float(entry.get("limit", 0))
            if limit <= 0:
                continue

            resets_at = None
            reset_str = entry.get("resetAt", "")
            if reset_str:
                try:
                    resets_at = datetime.fromisoformat(reset_str)
                except (ValueError, TypeError):
                    pass

            windows.append(
                UsageWindow(
                    label=label,
                    used_percent=min((used / limit) * 100, 100),
                    used=used,
                    total=limit,
                    remaining=limit - used,
                    resets_at=resets_at,
                    unit="次",
                )
            )

        return UsageData(
            provider_id=self.provider_id,
            provider_name=self.name,
            status=ProviderStatus.OK if windows else ProviderStatus.ERROR,
            plan_name=plan_name,
            windows=windows,
            error_message="" if windows else "无法解析用量数据",
            raw_response=data,
        )

    def get_display_config(self) -> dict[str, str]:
        return {"curl": "textarea"}

    @classmethod
    def parse_curl(cls, curl_text: str) -> dict[str, str]:
        """解析 curl 命令文本，返回提取的认证字段。"""
        from src.utils.curl_parser import parse_curl

        return parse_curl(curl_text)
