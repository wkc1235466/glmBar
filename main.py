"""GlmBar - Desktop widget for monitoring AI coding plan usage."""

from __future__ import annotations

import signal
import sys

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import QApplication

from src.config.settings import get_or_create_config, save_config
from src.providers.base import ProviderStatus, UsageData
from src.providers.registry import provider_registry
from src.ui.settings import SettingsWindow
from src.ui.tray import TrayIcon


class RefreshWorker(QThread):
    """Background thread to fetch usage data without blocking the UI."""

    result_ready = Signal(list)  # list[UsageData]

    def __init__(self, providers, parent=None):
        super().__init__(parent)
        self._providers = providers

    def run(self) -> None:
        import asyncio

        async def _fetch_all():
            tasks = [p.fetch_usage() for p in self._providers]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            usages: list[UsageData] = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    usages.append(
                        UsageData(
                            provider_id=self._providers[i].provider_id,
                            provider_name=self._providers[i].name,
                            status=ProviderStatus.ERROR,
                            error_message=str(result),
                        )
                    )
                else:
                    usages.append(result)
            return usages

        try:
            loop = asyncio.new_event_loop()
            usages = loop.run_until_complete(_fetch_all())
            loop.close()
            self.result_ready.emit(usages)
        except Exception as e:
            self.result_ready.emit([])


class GlmBarApp:
    """Main application controller."""

    def __init__(self) -> None:
        self._app = QApplication(sys.argv)
        self._app.setQuitOnLastWindowClosed(False)
        self._app.setApplicationName("GlmBar")

        # Allow Ctrl+C to work
        signal.signal(signal.SIGINT, signal.SIG_DFL)

        self._config = get_or_create_config()
        self._tray = TrayIcon()
        self._settings_window: SettingsWindow | None = None
        self._worker: RefreshWorker | None = None

        self._init_providers()

        # Refresh timer
        from PySide6.QtCore import QTimer

        self._timer = QTimer()
        self._timer.timeout.connect(self._refresh_all)
        self._timer.setInterval(self._config.refresh_interval_seconds * 1000)

        # Connect signals
        self._tray.refresh_requested.connect(self._refresh_all)
        self._tray.settings_requested.connect(self._show_settings)

        # Initial refresh
        QTimer.singleShot(500, self._refresh_all)

        # Show tray
        self._tray.show()

    def _init_providers(self) -> None:
        """Create provider instances from config."""
        for cfg in self._config.providers:
            if not cfg.enabled:
                continue

            cls = provider_registry.get_type(cfg.type)
            if cls:
                extra = dict(cfg.extra)
                provider = cls(api_key=cfg.api_key, **extra)
                provider.provider_id = cfg.id
                provider.name = cfg.name
            else:
                from src.providers.registry import CustomProvider

                provider = CustomProvider(
                    provider_id=cfg.id,
                    name=cfg.name,
                    api_key=cfg.api_key,
                    **cfg.extra,
                )

            provider_registry.add_instance(provider)

    def _refresh_all(self) -> None:
        """Fetch usage from all providers in a background thread."""
        providers = provider_registry.instances
        if not providers:
            self._tray.update_usage([])
            return

        # Skip if previous worker is still running
        if self._worker is not None and self._worker.isRunning():
            return

        self._worker = RefreshWorker(providers)
        self._worker.result_ready.connect(self._on_refresh_done)
        self._worker.start()

    def _on_refresh_done(self, usages: list) -> None:
        """Handle refresh results (called on main thread via signal)."""
        self._tray.update_usage(usages)

    def _show_settings(self) -> None:
        """Show the settings window."""
        if self._settings_window is not None and self._settings_window.isVisible():
            self._settings_window.raise_()
            self._settings_window.activateWindow()
            return

        self._settings_window = SettingsWindow(self._config)
        self._settings_window.config_changed.connect(self._on_config_changed)
        self._settings_window.show()

    def _on_config_changed(self) -> None:
        """Handle config changes from settings window."""
        save_config(self._config)

        # Rebuild providers
        provider_registry.clear_instances()
        self._init_providers()

        # Update timer interval
        self._timer.setInterval(self._config.refresh_interval_seconds * 1000)

        # Refresh immediately
        self._refresh_all()

    def run(self) -> int:
        """Start the application event loop."""
        self._timer.start()
        return self._app.exec()


def main() -> None:
    app = GlmBarApp()
    sys.exit(app.run())


if __name__ == "__main__":
    main()
