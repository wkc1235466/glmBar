"""MiniMax provider - China domestic version."""

from __future__ import annotations

import os

import httpx

from .base import BaseProvider, ProviderStatus, UsageData, UsageWindow


class MiniMaxProvider(BaseProvider):
    """MiniMax coding plan usage provider.

    Supports API token authentication with global and China endpoints.
    """

    DEFAULT_HOSTS = {
        "china": "https://platform.minimaxi.com",
        "global": "https://platform.minimax.io",
    }

    def __init__(self, api_key: str = "", region: str = "china", **kwargs):
        super().__init__(
            provider_id="minimax",
            name="MiniMax",
            description="MiniMax coding plan usage",
            requires_api_key=True,
            env_key="MINIMAX_API_KEY",
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

        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        }

        windows: list[UsageWindow] = []

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                # Primary: API token endpoint
                api_url = "https://api.minimax.io/v1/coding_plan/remains"
                try:
                    resp = await client.get(api_url, headers=headers)
                    if resp.status_code == 401:
                        return UsageData(
                            provider_id=self.provider_id,
                            provider_name=self.name,
                            status=ProviderStatus.UNAUTHORIZED,
                            error_message="API 密钥无效或已过期",
                        )
                    if resp.status_code == 200:
                        data = resp.json()
                        return self._parse_remains(data)
                except httpx.HTTPError:
                    pass

                # Fallback: platform remains API
                fallback_url = f"{self.base_url}/v1/api/openplatform/coding_plan/remains"
                resp = await client.get(fallback_url, headers=headers)
                resp.raise_for_status()
                return self._parse_remains(resp.json())

        except httpx.HTTPError as e:
            return UsageData(
                provider_id=self.provider_id,
                provider_name=self.name,
                status=ProviderStatus.ERROR,
                error_message=str(e),
            )

    def _parse_remains(self, data: dict) -> UsageData:
        # Parse model remains
        model_remains = data.get("model_remains", data.get("data", {}))

        if isinstance(model_remains, list):
            model_remains = model_remains[0] if model_remains else {}

        windows: list[UsageWindow] = []

        total = model_remains.get("total", 0)
        used = model_remains.get("used", 0)
        remaining = model_remains.get("remaining", 0)

        if total > 0:
            pct = (used / total) * 100
            windows.append(
                UsageWindow(
                    label="用量配额",
                    used_percent=min(pct, 100),
                    used=float(used),
                    total=float(total),
                    remaining=float(remaining),
                    unit="units",
                )
            )

        plan_name = data.get("plan_name", data.get("planName", ""))

        return UsageData(
            provider_id=self.provider_id,
            provider_name=self.name,
            status=ProviderStatus.OK if windows else ProviderStatus.ERROR,
            plan_name=plan_name,
            windows=windows,
            error_message="" if windows else "未找到用量数据",
            raw_response=data,
        )

    def get_display_config(self) -> dict[str, str]:
        return {
            "api_key": "password",
            "region": "select:china,global",
        }
