"""Alibaba Coding Plan (Bailian) provider."""

from __future__ import annotations

import os
from datetime import datetime, timezone

import httpx

from .base import BaseProvider, ProviderStatus, UsageData, UsageWindow


class AlibabaProvider(BaseProvider):
    """Alibaba Coding Plan usage provider.

    Supports API key and browser session authentication.
    Uses DashScope/Bailian console endpoints.
    """

    DEFAULT_HOSTS = {
        "china": "https://bailian.console.aliyun.com",
        "global": "https://modelstudio.console.alibabacloud.com",
    }

    def __init__(self, api_key: str = "", region: str = "china", **kwargs):
        super().__init__(
            provider_id="alibaba",
            name="阿里云百炼",
            description="Alibaba Cloud Bailian coding plan usage",
            requires_api_key=True,
            env_key="ALIBABA_CODING_PLAN_API_KEY",
            api_key=api_key,
            extra_config={"region": region},
            **kwargs,
        )
        self.region = region

    @property
    def base_url(self) -> str:
        region = self.extra_config.get("region", self.region)
        host = self.DEFAULT_HOSTS.get(region, region)
        if not host.startswith("http"):
            host = f"https://{host}"
        return host

    async def fetch_usage(self) -> UsageData:
        token = self.get_api_key()
        if not token:
            return UsageData(
                provider_id=self.provider_id,
                provider_name=self.name,
                status=ProviderStatus.NO_API_KEY,
            )

        url = (
            f"{self.base_url}/data/api.json"
            "?action=zeldaEasy.broadscope-bailian.codingPlan.queryCodingPlanInstanceInfoV2"
            "&product=broadscope-bailian&api=queryCodingPlanInstanceInfoV2"
        )
        headers = {
            "Authorization": f"Bearer {token}",
            "x-api-key": token,
            "X-DashScope-API-Key": token,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        payload = {}

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(url, headers=headers, json=payload)

                if resp.status_code == 401:
                    # Try fallback region
                    return await self._try_fallback(client, token)

                resp.raise_for_status()
                data = resp.json()

                # Check for console login required
                if data.get("Code") == "ConsoleNeedLogin":
                    return UsageData(
                        provider_id=self.provider_id,
                        provider_name=self.name,
                        status=ProviderStatus.ERROR,
                        error_message="需要控制台登录 - 此账号不支持 API 密钥模式",
                    )

                return self._parse_response(data)

        except httpx.HTTPError as e:
            return UsageData(
                provider_id=self.provider_id,
                provider_name=self.name,
                status=ProviderStatus.ERROR,
                error_message=str(e),
            )

    async def _try_fallback(self, client: httpx.AsyncClient, token: str) -> UsageData:
        """Try the alternate region as fallback."""
        current = self.extra_config.get("region", self.region)
        fallback = "global" if current == "china" else "china"
        host = self.DEFAULT_HOSTS[fallback]

        url = (
            f"{host}/data/api.json"
            "?action=zeldaEasy.broadscope-bailian.codingPlan.queryCodingPlanInstanceInfoV2"
            "&product=broadscope-bailian&api=queryCodingPlanInstanceInfoV2"
        )
        headers = {
            "Authorization": f"Bearer {token}",
            "x-api-key": token,
            "X-DashScope-API-Key": token,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        try:
            resp = await client.post(url, headers=headers, json={})
            resp.raise_for_status()
            data = resp.json()
            if data.get("Code") == "ConsoleNeedLogin":
                return UsageData(
                    provider_id=self.provider_id,
                    provider_name=self.name,
                    status=ProviderStatus.ERROR,
                    error_message="两个区域均需要控制台登录",
                )
            return self._parse_response(data)
        except httpx.HTTPError:
            return UsageData(
                provider_id=self.provider_id,
                provider_name=self.name,
                status=ProviderStatus.UNAUTHORIZED,
                error_message="API 密钥无效或已过期",
            )

    def _parse_response(self, data: dict) -> UsageData:
        windows: list[UsageWindow] = []

        instances = data.get("codingPlanInstanceInfos", [])
        if not instances:
            # Try nested data
            inner = data.get("Data", {})
            if isinstance(inner, dict):
                instances = inner.get("codingPlanInstanceInfos", [])

        plan_name = ""
        for inst in instances:
            plan_name = (
                inst.get("planName")
                or inst.get("instanceName")
                or inst.get("packageName")
                or plan_name
            )

            quota = inst.get("codingPlanQuotaInfo", {})
            if not quota:
                continue

            # 5-hour window
            h5_used = quota.get("per5HourUsedQuota", 0)
            h5_total = quota.get("per5HourTotalQuota", 0)
            h5_reset = quota.get("per5HourQuotaNextRefreshTime", "")
            if h5_total > 0:
                windows.append(
                    UsageWindow(
                        label="5小时配额",
                        used_percent=min((h5_used / h5_total) * 100, 100),
                        used=float(h5_used),
                        total=float(h5_total),
                        remaining=float(h5_total - h5_used),
                        resets_at=self._parse_time(h5_reset),
                        unit="units",
                    )
                )

            # Weekly window
            wk_used = quota.get("perWeekUsedQuota", 0)
            wk_total = quota.get("perWeekTotalQuota", 0)
            wk_reset = quota.get("perWeekQuotaNextRefreshTime", "")
            if wk_total > 0:
                windows.append(
                    UsageWindow(
                        label="每周配额",
                        used_percent=min((wk_used / wk_total) * 100, 100),
                        used=float(wk_used),
                        total=float(wk_total),
                        remaining=float(wk_total - wk_used),
                        resets_at=self._parse_time(wk_reset),
                        unit="units",
                    )
                )

            # Monthly window
            mo_used = quota.get("perBillMonthUsedQuota", 0)
            mo_total = quota.get("perBillMonthTotalQuota", 0)
            mo_reset = quota.get("perBillMonthQuotaNextRefreshTime", "")
            if mo_total > 0:
                windows.append(
                    UsageWindow(
                        label="每月配额",
                        used_percent=min((mo_used / mo_total) * 100, 100),
                        used=float(mo_used),
                        total=float(mo_total),
                        remaining=float(mo_total - mo_used),
                        resets_at=self._parse_time(mo_reset),
                        unit="units",
                    )
                )

        return UsageData(
            provider_id=self.provider_id,
            provider_name=self.name,
            status=ProviderStatus.OK if windows else ProviderStatus.ERROR,
            plan_name=plan_name,
            windows=windows,
            error_message="" if windows else "未找到配额数据",
            raw_response=data,
        )

    @staticmethod
    def _parse_time(value: str) -> datetime | None:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return None

    def get_display_config(self) -> dict[str, str]:
        return {
            "api_key": "password",
            "region": "select:china,global",
        }
