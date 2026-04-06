"""Z.ai (Zhipu/BigModel) provider - China domestic version."""

from __future__ import annotations

import os
from datetime import datetime, timezone

from .base import BaseProvider, ProviderStatus, UsageData, UsageWindow


class ZaiProvider(BaseProvider):
    """Z.ai (Zhipu BigModel) coding plan usage provider.

    Supports both global (api.z.ai) and China (open.bigmodel.cn) endpoints.
    """

    DEFAULT_HOSTS = {
        "china": "https://open.bigmodel.cn",
        "global": "https://api.z.ai",
    }

    def __init__(self, api_key: str = "", region: str = "china", **kwargs):
        super().__init__(
            provider_id="zai",
            name="Z.ai (智谱)",
            description="智谱 BigModel coding plan usage",
            requires_api_key=True,
            env_key="Z_AI_API_KEY",
            api_key=api_key,
            extra_config={"region": region},
            **kwargs,
        )
        self.region = region

    @property
    def base_url(self) -> str:
        host = self.extra_config.get("region", self.region)
        if host in self.DEFAULT_HOSTS:
            host = self.DEFAULT_HOSTS[host]
        if not host.startswith("http"):
            host = f"https://{host}"
        custom_url = os.environ.get("Z_AI_QUOTA_URL")
        if custom_url:
            return custom_url
        return host

    async def fetch_usage(self) -> UsageData:
        token = self.get_api_key()
        if not token:
            return self._no_key_result()

        url = f"{self.base_url}/api/monitor/usage/quota/limit"
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        }

        result = await self._http_get(url, headers)
        if isinstance(result, UsageData):
            return result
        return self._parse_response(result)

    def _parse_response(self, data: dict) -> UsageData:
        code = data.get("code", -1)
        if code != 200:
            return self._error_result(data.get("msg", f"API 错误码: {code}"))

        payload = data.get("data", {})
        plan_name = (
            payload.get("planName")
            or payload.get("plan")
            or payload.get("packageName")
            or ""
        )

        windows: list[UsageWindow] = []
        for limit in payload.get("limits", []):
            limit_type = limit.get("type", "")
            usage = limit.get("usage", 0)
            number = limit.get("number", 0)
            remaining = limit.get("remaining", 0)
            current_value = limit.get("currentValue", usage)
            percentage = limit.get("percentage")

            unit_num = limit.get("unit", 1)
            # unit represents duration: 1=minute, 5=minutes, 60=hour etc.
            # The number field is the window size
            window_size = number

            resets_at = None
            reset_ms = limit.get("nextResetTime")
            if reset_ms:
                try:
                    resets_at = datetime.fromtimestamp(reset_ms / 1000, tz=timezone.utc)
                except (OSError, ValueError):
                    pass

            if percentage is None and window_size > 0:
                percentage = (current_value / window_size) * 100

            label = "Token 配额"
            if limit_type == "TIME_LIMIT":
                label = "MCP/时间配额"
            elif limit_type == "TOKENS_LIMIT":
                label = "Token 配额"

            unit = "次" if limit_type == "TIME_LIMIT" else "tokens"

            windows.append(
                UsageWindow(
                    label=label,
                    used_percent=min(percentage or 0, 100),
                    used=float(current_value),
                    total=float(window_size),
                    remaining=float(remaining),
                    resets_at=resets_at,
                    unit=unit,
                )
            )

        # Token 配额排在前面，MCP/时间配额排在后面
        windows.sort(key=lambda w: 0 if "Token" in w.label else 1)

        return UsageData(
            provider_id=self.provider_id,
            provider_name=self.name,
            status=ProviderStatus.OK,
            plan_name=plan_name,
            windows=windows,
            raw_response=data,
        )

    def get_display_config(self) -> dict[str, str]:
        return {
            "api_key": "password",
            "region": "select:china,global",
        }
