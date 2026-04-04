"""Provider registry for managing and dynamically adding providers."""

from __future__ import annotations

from typing import Type

from .base import BaseProvider
from .zai import ZaiProvider
from .minimax import MiniMaxProvider
from .kimi import KimiProvider
from .alibaba import AlibabaProvider
from .openrouter import OpenRouterProvider
from .baidu import BaiduQianfanProvider


class ProviderRegistry:
    """Registry of available provider types and active provider instances."""

    def __init__(self) -> None:
        self._types: dict[str, Type[BaseProvider]] = {}
        self._instances: dict[str, BaseProvider] = {}

        # Register built-in providers
        self.register_type("zai", ZaiProvider)
        self.register_type("minimax", MiniMaxProvider)
        self.register_type("kimi", KimiProvider)
        self.register_type("alibaba", AlibabaProvider)
        self.register_type("openrouter", OpenRouterProvider)
        self.register_type("baidu", BaiduQianfanProvider)

    def register_type(self, type_id: str, cls: Type[BaseProvider]) -> None:
        """Register a provider class by type ID."""
        self._types[type_id] = cls

    def get_type(self, type_id: str) -> Type[BaseProvider] | None:
        """Get a provider class by type ID."""
        return self._types.get(type_id)

    @property
    def available_types(self) -> dict[str, Type[BaseProvider]]:
        """Return all registered provider types."""
        return dict(self._types)

    def add_instance(self, provider: BaseProvider) -> None:
        """Add or update a provider instance."""
        self._instances[provider.provider_id] = provider

    def remove_instance(self, provider_id: str) -> None:
        """Remove a provider instance."""
        self._instances.pop(provider_id, None)

    def get_instance(self, provider_id: str) -> BaseProvider | None:
        """Get a provider instance by ID."""
        return self._instances.get(provider_id)

    @property
    def instances(self) -> list[BaseProvider]:
        """Return all active provider instances."""
        return list(self._instances.values())

    def create_provider(
        self,
        type_id: str,
        provider_id: str,
        name: str,
        api_key: str = "",
        **kwargs,
    ) -> BaseProvider:
        """Create a new provider instance.

        For built-in types, uses the registered class.
        For custom types, creates a generic CustomProvider.
        """
        cls = self._types.get(type_id)
        if cls:
            provider = cls(api_key=api_key, **kwargs)
            # Override ID and name if they differ from defaults
            if provider_id:
                provider.provider_id = provider_id
            if name:
                provider.name = name
        else:
            # Custom provider with user-specified endpoint
            provider = CustomProvider(
                provider_id=provider_id,
                name=name,
                api_key=api_key,
                **kwargs,
            )
        return provider


class CustomProvider(BaseProvider):
    """Generic custom provider for user-added platforms.

    Expects a quota_url config field pointing to a GET endpoint
    that returns JSON with usage data.
    """

    def __init__(self, provider_id: str, name: str, api_key: str = "", **kwargs):
        super().__init__(
            provider_id=provider_id,
            name=name,
            description=f"Custom provider: {name}",
            requires_api_key=True,
            api_key=api_key,
            extra_config=kwargs,
        )

    async def fetch_usage(self) -> None:
        from .base import UsageData, ProviderStatus

        token = self.get_api_key()
        if not token:
            return UsageData(
                provider_id=self.provider_id,
                provider_name=self.name,
                status=ProviderStatus.NO_API_KEY,
            )

        url = self.extra_config.get("quota_url", "")
        if not url:
            return UsageData(
                provider_id=self.provider_id,
                provider_name=self.name,
                status=ProviderStatus.ERROR,
                error_message="未配置配额查询 URL",
            )

        import httpx

        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(url, headers=headers)
                resp.raise_for_status()
                data = resp.json()
                return self._parse_generic(data)
        except httpx.HTTPError as e:
            return UsageData(
                provider_id=self.provider_id,
                provider_name=self.name,
                status=ProviderStatus.ERROR,
                error_message=str(e),
            )

    def _parse_generic(self, data: dict):
        """Try to extract usage from common response patterns."""
        from .base import UsageData, ProviderStatus, UsageWindow

        windows: list[UsageWindow] = []

        # Try common patterns
        for key in ("data", "usage", "quota", "limits"):
            entry = data.get(key)
            if isinstance(entry, dict):
                used = float(entry.get("used", entry.get("usage", 0)))
                total = float(entry.get("total", entry.get("limit", entry.get("quota", 0))))
                if total > 0:
                    windows.append(UsageWindow(
                        label="Usage",
                        used_percent=min((used / total) * 100, 100),
                        used=used,
                        total=total,
                        remaining=total - used,
                    ))
                break
            elif isinstance(entry, list):
                for item in entry[:3]:
                    used = float(item.get("used", item.get("usage", 0)))
                    total = float(item.get("total", item.get("limit", item.get("number", 0))))
                    label = item.get("type", item.get("label", "Usage"))
                    if total > 0:
                        windows.append(UsageWindow(
                            label=label,
                            used_percent=min((used / total) * 100, 100),
                            used=used,
                            total=total,
                            remaining=total - used,
                        ))
                break

        return UsageData(
            provider_id=self.provider_id,
            provider_name=self.name,
            status=ProviderStatus.OK if windows else ProviderStatus.ERROR,
            windows=windows,
            raw_response=data,
            error_message="" if windows else "无法解析响应中的用量数据",
        )

    def get_display_config(self) -> dict[str, str]:
        return {
            "api_key": "password",
            "quota_url": "text",
        }


# Global singleton
provider_registry = ProviderRegistry()
