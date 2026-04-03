"""Kimi (Moonshot) provider - China domestic version."""

from __future__ import annotations

import os
from datetime import datetime, timezone

import httpx

from .base import BaseProvider, ProviderStatus, UsageData, UsageWindow


class KimiProvider(BaseProvider):
    """Kimi For Coding usage provider.

    Uses JWT Bearer token from kimi-auth cookie or manual entry.
    Shows weekly request quota and 5-hour rate limit.
    """

    def __init__(self, api_key: str = "", **kwargs):
        super().__init__(
            provider_id="kimi",
            name="Kimi (月之暗面)",
            description="Kimi For Coding usage",
            requires_api_key=True,
            env_key="KIMI_AUTH_TOKEN",
            api_key=api_key,
            **kwargs,
        )

    async def fetch_usage(self) -> UsageData:
        token = self.get_api_key()
        if not token:
            return UsageData(
                provider_id=self.provider_id,
                provider_name=self.name,
                status=ProviderStatus.NO_API_KEY,
            )

        url = "https://www.kimi.com/apiv2/kimi.gateway.billing.v1.BillingService/GetUsages"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        payload = {}

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(url, headers=headers, json=payload)

                if resp.status_code == 401:
                    return UsageData(
                        provider_id=self.provider_id,
                        provider_name=self.name,
                        status=ProviderStatus.UNAUTHORIZED,
                        error_message="认证令牌无效或已过期",
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

        return self._parse_response(data)

    def _parse_response(self, data: dict) -> UsageData:
        usages = data.get("usages", [])
        windows: list[UsageWindow] = []

        for usage_entry in usages:
            if usage_entry.get("scope") != "FEATURE_CODING":
                continue

            # Primary: weekly quota
            detail = usage_entry.get("detail", {})
            limit = float(detail.get("limit", 0))
            used = float(detail.get("used", 0))
            remaining = float(detail.get("remaining", 0))
            reset_time = detail.get("resetTime", "")

            if limit > 0:
                resets_at = None
                if reset_time:
                    try:
                        resets_at = datetime.fromisoformat(
                            reset_time.replace("Z", "+00:00")
                        )
                    except (ValueError, TypeError):
                        pass

                windows.append(
                    UsageWindow(
                        label="每周配额",
                        used_percent=min((used / limit) * 100, 100),
                        used=used,
                        total=limit,
                        remaining=remaining,
                        resets_at=resets_at,
                        unit="requests",
                    )
                )

            # Secondary: 5-hour rate limit
            for sub_limit in usage_entry.get("limits", []):
                window = sub_limit.get("window", {})
                sub_detail = sub_limit.get("detail", {})
                sub_limit_val = float(sub_detail.get("limit", 0))
                sub_used = float(sub_detail.get("used", 0))
                sub_remaining = float(sub_detail.get("remaining", 0))
                sub_reset = sub_detail.get("resetTime", "")

                if sub_limit_val > 0:
                    resets_at = None
                    if sub_reset:
                        try:
                            resets_at = datetime.fromisoformat(
                                sub_reset.replace("Z", "+00:00")
                            )
                        except (ValueError, TypeError):
                            pass

                    duration = window.get("duration", 300)
                    time_unit = window.get("timeUnit", "")
                    label = f"{duration // 60}小时限流" if duration >= 60 else f"{duration}分钟限流"

                    windows.append(
                        UsageWindow(
                            label=label,
                            used_percent=min((sub_used / sub_limit_val) * 100, 100),
                            used=sub_used,
                            total=sub_limit_val,
                            remaining=sub_remaining,
                            resets_at=resets_at,
                            unit="requests",
                        )
                    )

        return UsageData(
            provider_id=self.provider_id,
            provider_name=self.name,
            status=ProviderStatus.OK if windows else ProviderStatus.ERROR,
            plan_name="Kimi 编程版",
            windows=windows,
            error_message="" if windows else "未找到编程用量数据",
            raw_response=data,
        )

    def get_display_config(self) -> dict[str, str]:
        return {
            "api_key": "password",
        }
