"""Base provider classes and data models for usage tracking."""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class ProviderStatus(str, Enum):
    OK = "ok"
    ERROR = "error"
    NO_API_KEY = "no_api_key"
    UNAUTHORIZED = "unauthorized"


@dataclass
class UsageWindow:
    """A single usage window (e.g. 5-hour rate limit, weekly quota)."""
    label: str  # e.g. "Token Quota", "5h Rate Limit"
    used_percent: float  # 0.0 - 100.0
    used: float = 0.0
    total: float = 0.0
    remaining: float = 0.0
    resets_at: datetime | None = None
    unit: str = ""  # e.g. "requests", "tokens", "%"


@dataclass
class UsageData:
    """Aggregated usage data from a provider."""
    provider_id: str
    provider_name: str
    status: ProviderStatus = ProviderStatus.OK
    plan_name: str = ""
    windows: list[UsageWindow] = field(default_factory=list)
    balance: float | None = None  # for credit-based providers
    plan_expires: str | None = None  # e.g. "2026-08-23"
    account: str = ""
    error_message: str = ""
    raw_response: dict[str, Any] | None = None
    updated_at: datetime = field(default_factory=datetime.now)

    @property
    def primary_percent(self) -> float | None:
        """Return the primary usage percentage (first window)."""
        if self.windows:
            return self.windows[0].used_percent
        return None

    @property
    def summary_text(self) -> str:
        """Short summary for tray display."""
        if self.status == ProviderStatus.NO_API_KEY:
            return "未设置密钥"
        if self.status == ProviderStatus.ERROR:
            return "错误"
        if self.status == ProviderStatus.UNAUTHORIZED:
            return "认证失败"
        if not self.windows:
            return "暂无数据"
        w = self.windows[0]
        return f"{w.used_percent:.0f}%"


class BaseProvider(abc.ABC):
    """Abstract base class for all usage providers."""

    def __init__(
        self,
        provider_id: str,
        name: str,
        description: str = "",
        requires_api_key: bool = True,
        env_key: str = "",
        api_key: str = "",
        extra_config: dict[str, Any] | None = None,
        **kwargs,  # Accept additional config fields
    ):
        self.provider_id = provider_id
        self.name = name
        self.description = description
        self.requires_api_key = requires_api_key
        self.env_key = env_key
        self.api_key = api_key
        # Merge explicit extra_config with any additional kwargs
        self.extra_config = extra_config or {}
        self.extra_config.update(kwargs)

    def get_api_key(self) -> str | None:
        """Get API key from instance or environment variable."""
        import os

        if self.api_key:
            return self.api_key
        if self.env_key:
            return os.environ.get(self.env_key)
        return None

    @abc.abstractmethod
    async def fetch_usage(self) -> UsageData:
        """Fetch usage data from the provider API."""
        ...

    def _no_key_result(self) -> UsageData:
        """Return a standard NO_API_KEY result."""
        return UsageData(
            provider_id=self.provider_id,
            provider_name=self.name,
            status=ProviderStatus.NO_API_KEY,
        )

    def _error_result(self, message: str, raw: dict | None = None) -> UsageData:
        """Return a standard ERROR result."""
        return UsageData(
            provider_id=self.provider_id,
            provider_name=self.name,
            status=ProviderStatus.ERROR,
            error_message=message,
            raw_response=raw,
        )

    def _unauthorized_result(self, message: str = "API 密钥无效或已过期") -> UsageData:
        """Return a standard UNAUTHORIZED result."""
        return UsageData(
            provider_id=self.provider_id,
            provider_name=self.name,
            status=ProviderStatus.UNAUTHORIZED,
            error_message=message,
        )

    async def _http_get(
        self,
        url: str,
        headers: dict[str, str],
        *,
        timeout: int = 15,
    ) -> UsageData | dict:
        """Perform a GET request with standard error handling.

        Returns parsed JSON dict on success, or a UsageData error on failure.
        The caller should check the return type.
        """
        import httpx

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.get(url, headers=headers)
                if resp.status_code == 401:
                    return self._unauthorized_result()
                resp.raise_for_status()
                return resp.json()
        except httpx.HTTPError as e:
            return self._error_result(str(e))

    async def _http_post(
        self,
        url: str,
        headers: dict[str, str],
        *,
        payload: dict = {},
        timeout: int = 15,
    ) -> UsageData | dict:
        """Perform a POST request with standard error handling.

        Returns parsed JSON dict on success, or a UsageData error on failure.
        """
        import httpx

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(url, headers=headers, json=payload)
                if resp.status_code == 401:
                    return self._unauthorized_result()
                resp.raise_for_status()
                return resp.json()
        except httpx.HTTPError as e:
            return self._error_result(str(e))

    def get_display_config(self) -> dict[str, str]:
        """Return config fields for UI rendering.
        Returns dict of field_name -> field_type (text, password, select).
        """
        return {}
