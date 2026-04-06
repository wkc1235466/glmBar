"""OpenRouter provider - unified API gateway."""

from __future__ import annotations

import os

import httpx

from .base import BaseProvider, ProviderStatus, UsageData, UsageWindow


class OpenRouterProvider(BaseProvider):
    """OpenRouter usage provider.

    Shows credit balance and usage from OpenRouter's unified API.
    """

    def __init__(self, api_key: str = "", **kwargs):
        super().__init__(
            provider_id="openrouter",
            name="OpenRouter",
            description="OpenRouter unified API credit tracking",
            requires_api_key=True,
            env_key="OPENROUTER_API_KEY",
            api_key=api_key,
            **kwargs,
        )

    @property
    def base_url(self) -> str:
        return os.environ.get(
            "OPENROUTER_API_URL", "https://openrouter.ai/api/v1"
        )

    async def fetch_usage(self) -> UsageData:
        token = self.get_api_key()
        if not token:
            return self._no_key_result()

        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                # Fetch credits
                credits_result = await self._http_get(
                    f"{self.base_url}/credits", headers
                )
                if isinstance(credits_result, UsageData):
                    return credits_result
                credits_data = credits_result

                # Fetch key info for rate limits
                key_data = {}
                try:
                    key_resp = await client.get(
                        f"{self.base_url}/key", headers=headers
                    )
                    if key_resp.status_code == 200:
                        key_data = key_resp.json()
                except httpx.HTTPError:
                    pass

                return self._parse_response(credits_data, key_data)

        except httpx.HTTPError as e:
            return self._error_result(str(e))

    def _parse_response(self, credits: dict, key_data: dict) -> UsageData:
        total_credits = float(credits.get("total_credits", 0))
        total_usage = float(credits.get("total_usage", 0))
        balance = total_credits - total_usage

        windows: list[UsageWindow] = []
        if total_credits > 0:
            pct = (total_usage / total_credits) * 100
            windows.append(
                UsageWindow(
                    label="额度用量",
                    used_percent=min(pct, 100),
                    used=total_usage,
                    total=total_credits,
                    remaining=balance,
                    unit="USD",
                )
            )

        # Rate limit from key data
        limit = key_data.get("limit", key_data.get("rate_limit", {}))
        if isinstance(limit, dict):
            req_limit = limit.get("requests", 0)
            req_used = limit.get("usage", 0)
            if req_limit > 0:
                windows.append(
                    UsageWindow(
                        label="速率限制",
                        used_percent=min((req_used / req_limit) * 100, 100),
                        used=float(req_used),
                        total=float(req_limit),
                        remaining=float(req_limit - req_used),
                        unit="requests",
                    )
                )

        return UsageData(
            provider_id=self.provider_id,
            provider_name=self.name,
            status=ProviderStatus.OK if windows else ProviderStatus.ERROR,
            plan_name="OpenRouter",
            windows=windows,
            balance=balance,
            error_message="" if windows else "未找到额度数据",
            raw_response={"credits": credits, "key": key_data},
        )

    def get_display_config(self) -> dict[str, str]:
        return {
            "api_key": "password",
        }
