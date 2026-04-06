"""MiniMax provider - China domestic version."""

from __future__ import annotations

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
            return self._no_key_result()

        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        }

        import httpx

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                # Primary: API token endpoint
                api_url = "https://api.minimax.io/v1/coding_plan/remains"
                result = await self._http_get(api_url, headers)
                if isinstance(result, UsageData):
                    if result.status == ProviderStatus.UNAUTHORIZED:
                        return result
                    # Non-401 error: try fallback
                else:
                    return self._parse_remains(result)

                # Fallback: platform remains API
                fallback_url = f"{self.base_url}/v1/api/openplatform/coding_plan/remains"
                fallback_result = await self._http_get(fallback_url, headers)
                if isinstance(fallback_result, UsageData):
                    return fallback_result
                return self._parse_remains(fallback_result)

        except httpx.HTTPError as e:
            return self._error_result(str(e))

    def _parse_remains(self, data: dict) -> UsageData:
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
