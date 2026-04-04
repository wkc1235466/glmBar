"""Configuration management for GlmBar."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

CONFIG_DIR = Path.home() / ".glmbar"
CONFIG_FILE = CONFIG_DIR / "config.json"


class ProviderConfig(BaseModel):
    """Configuration for a single provider instance."""
    id: str
    type: str  # provider type (zai, minimax, kimi, etc.)
    name: str
    enabled: bool = True
    api_key: str = ""
    extra: dict[str, Any] = Field(default_factory=dict)


class AppConfig(BaseModel):
    """Application-level configuration."""
    refresh_interval_seconds: int = 60
    providers: list[ProviderConfig] = Field(default_factory=list)
    # UI settings
    always_on_top: bool = True
    show_window_on_start: bool = False
    compact_mode: bool = False


def load_config() -> AppConfig:
    """Load configuration from disk, creating defaults if needed."""
    if CONFIG_FILE.exists():
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            return AppConfig.model_validate(data)
        except (json.JSONDecodeError, Exception):
            pass
    return AppConfig()


def save_config(config: AppConfig) -> None:
    """Save configuration to disk."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(
        config.model_dump_json(indent=2), encoding="utf-8"
    )


def get_or_create_config() -> AppConfig:
    """Get existing config or create default with all built-in providers."""
    config = load_config()
    if not config.providers:
        config.providers = [
            ProviderConfig(id="zai", type="zai", name="Z.ai (智谱)"),
            ProviderConfig(id="minimax", type="minimax", name="MiniMax"),
            ProviderConfig(id="kimi", type="kimi", name="Kimi (月之暗面)"),
            ProviderConfig(id="alibaba", type="alibaba", name="阿里云百炼"),
            ProviderConfig(id="openrouter", type="openrouter", name="OpenRouter"),
            ProviderConfig(id="baidu", type="baidu", name="百度千帆"),
            ProviderConfig(id="baidu", type="baidu", name="百度千帆"),
        ]
        save_config(config)
    return config
