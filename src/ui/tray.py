"""System tray icon and usage display widget."""

from __future__ import annotations

import sys
from datetime import datetime, timezone

from PySide6.QtCore import QPoint, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QColor, QFont, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QProgressBar,
    QScrollArea,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from src.providers.base import ProviderStatus, UsageData


def create_usage_icon(percent: float | None, status: ProviderStatus = ProviderStatus.OK) -> QPixmap:
    """Create a tray icon showing usage percentage as a colored arc."""
    size = 64
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    # Background circle
    painter.setPen(QPen(QColor(60, 60, 60), 4))
    painter.drawArc(8, 8, size - 16, size - 16, 0, 360 * 16)

    # Usage arc
    if percent is not None and status == ProviderStatus.OK:
        if percent < 50:
            color = QColor(76, 175, 80)  # green
        elif percent < 80:
            color = QColor(255, 193, 7)  # yellow
        else:
            color = QColor(244, 67, 54)  # red

        painter.setPen(QPen(color, 4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        span = int(percent / 100 * 360 * 16)
        painter.drawArc(8, 8, size - 16, size - 16, 90 * 16, -span)

        # Center text
        font = QFont("Segoe UI", 12, QFont.Weight.Bold)
        painter.setFont(font)
        painter.setPen(QColor(220, 220, 220))
        painter.drawText(
            pixmap.rect(),
            Qt.AlignmentFlag.AlignCenter,
            f"{percent:.0f}",
        )
    else:
        # Error/no key state
        color = QColor(120, 120, 120)
        painter.setPen(QPen(color, 3))
        font = QFont("Segoe UI", 18, QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "?")

    painter.end()
    return pixmap


class UsageBar(QProgressBar):
    """A styled progress bar for usage display."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(8)
        self.setTextVisible(False)
        self.setMinimum(0)
        self.setMaximum(100)
        self._set_color(0)

    def set_percent(self, value: float) -> None:
        self.setValue(int(value))
        self._set_color(value)

    def _set_color(self, pct: float) -> None:
        if pct < 50:
            color = "#4CAF50"
        elif pct < 80:
            color = "#FFC107"
        else:
            color = "#F44336"
        self.setStyleSheet(
            f"QProgressBar {{ background: #2a2a2a; border-radius: 4px; border: none; }}"
            f"QProgressBar::chunk {{ background: {color}; border-radius: 4px; }}"
        )


class ProviderCard(QFrame):
    """A card widget showing one provider's usage info."""

    def __init__(self, usage: UsageData, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet(
            "ProviderCard { background: #1e1e2e; border: 1px solid #333; "
            "border-radius: 8px; padding: 8px; }"
        )
        self._build(usage)

    def _build(self, usage: UsageData) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(4)

        # Header: name + status
        header = QHBoxLayout()

        name_label = QLabel(usage.provider_name)
        name_label.setStyleSheet("color: #e0e0e0; font-size: 14px; font-weight: bold;")
        header.addWidget(name_label)

        header.addStretch()

        status_text = usage.summary_text
        status_color = "#4CAF50"
        if usage.status == ProviderStatus.ERROR:
            status_color = "#F44336"
        elif usage.status == ProviderStatus.NO_API_KEY:
            status_color = "#888"
        elif usage.status == ProviderStatus.UNAUTHORIZED:
            status_color = "#FF9800"

        status_label = QLabel(status_text)
        status_label.setStyleSheet(f"color: {status_color}; font-size: 12px;")
        header.addWidget(status_label)

        layout.addLayout(header)

        # Plan name
        if usage.plan_name:
            plan = QLabel(f"套餐: {usage.plan_name}")
            plan.setStyleSheet("color: #888; font-size: 11px;")
            layout.addWidget(plan)

        # Error message
        if usage.error_message:
            err = QLabel(usage.error_message)
            err.setStyleSheet("color: #FF9800; font-size: 11px;")
            err.setWordWrap(True)
            layout.addWidget(err)

        # Usage windows
        for w in usage.windows:
            win_layout = QVBoxLayout()
            win_layout.setSpacing(2)

            info = QHBoxLayout()
            lbl = QLabel(w.label)
            lbl.setStyleSheet("color: #aaa; font-size: 11px;")
            info.addWidget(lbl)

            info.addStretch()

            detail_parts = [f"{w.used:.0f}/{w.total:.0f}"]
            if w.unit:
                detail_parts.append(w.unit)
            if w.resets_at:
                from datetime import timezone
                delta = w.resets_at - datetime.now(timezone.utc)
                if delta.total_seconds() > 0:
                    hours = int(delta.total_seconds() // 3600)
                    mins = int((delta.total_seconds() % 3600) // 60)
                    detail_parts.append(f"{hours}时{mins}分后重置")

            detail = QLabel(" ".join(detail_parts))
            detail.setStyleSheet("color: #888; font-size: 10px;")
            info.addWidget(detail)

            win_layout.addLayout(info)

            bar = UsageBar()
            bar.set_percent(w.used_percent)
            win_layout.addWidget(bar)

            layout.addLayout(win_layout)

        # Balance (for credit-based providers)
        if usage.balance is not None:
            bal = QLabel(f"余额: ${usage.balance:.2f}")
            bal.setStyleSheet("color: #4CAF50; font-size: 11px;")
            layout.addWidget(bal)

        # Updated time
        time_str = usage.updated_at.strftime("%H:%M:%S")
        updated = QLabel(f"更新时间: {time_str}")
        updated.setStyleSheet("color: #555; font-size: 10px;")
        layout.addWidget(updated)


class UsagePopup(QWidget):
    """Popup window that appears when clicking the tray icon.

    Uses Qt.Tool instead of Qt.Popup for better Windows compatibility.
    """

    closed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedWidth(380)
        self.setStyleSheet("background: transparent;")
        self._auto_close_timer = QTimer(self)
        self._auto_close_timer.setSingleShot(True)
        self._auto_close_timer.setInterval(100)
        self._auto_close_timer.timeout.connect(self._check_focus)

        self._container = QFrame(self)
        self._container.setStyleSheet(
            "QFrame { background: #12121e; border: 1px solid #333; "
            "border-radius: 12px; }"
        )

        self._main_layout = QVBoxLayout(self)
        self._main_layout.setContentsMargins(0, 0, 0, 0)
        self._main_layout.addWidget(self._container)

        self._layout = QVBoxLayout(self._container)
        self._layout.setContentsMargins(16, 12, 16, 12)
        self._layout.setSpacing(8)

        # Title
        title = QLabel("GlmBar - 编程套餐用量")
        title.setStyleSheet("color: #e0e0e0; font-size: 16px; font-weight: bold;")
        self._layout.addWidget(title)

        # Cards container inside a scroll area
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setStyleSheet("QScrollArea { background: transparent; }")
        self._scroll.setMaximumHeight(500)

        self._cards_widget = QWidget()
        self._cards_widget.setStyleSheet("background: transparent;")
        self._cards_layout = QVBoxLayout(self._cards_widget)
        self._cards_layout.setSpacing(8)
        self._cards_layout.setContentsMargins(0, 0, 0, 0)
        self._scroll.setWidget(self._cards_widget)

        self._layout.addWidget(self._scroll)

        # Footer
        self._footer = QLabel("左键点击：刷新 | 右键点击：设置")
        self._footer.setStyleSheet("color: #555; font-size: 10px;")
        self._layout.addWidget(self._footer)

    def update_usage(self, usages: list[UsageData]) -> None:
        """Update the display with new usage data."""
        # Clear existing cards
        while self._cards_layout.count():
            item = self._cards_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not usages:
            empty = QLabel("暂无已配置的服务商")
            empty.setStyleSheet("color: #888; font-size: 13px;")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._cards_layout.addWidget(empty)
        else:
            for usage in usages:
                card = ProviderCard(usage)
                self._cards_layout.addWidget(card)

        self._cards_layout.addStretch()
        self._cards_widget.adjustSize()
        self.adjustSize()

    def show_at_tray(self) -> None:
        """Show the popup positioned near the system tray."""
        screen = QApplication.primaryScreen().geometry()
        # Position at bottom-right of screen (where tray usually is)
        w = self.sizeHint().width()
        h = self.sizeHint().height()
        x = screen.right() - w - 16
        y = screen.bottom() - h - 60  # above taskbar

        self.move(x, y)
        self.show()
        self.raise_()
        self.activateWindow()
        self._auto_close_timer.start()

    def _check_focus(self) -> None:
        """Check if focus moved away from popup, close if so."""
        if not self.isActiveWindow():
            self.hide()
            self.closed.emit()
            return
        self._auto_close_timer.start()

    def hide(self) -> None:
        self._auto_close_timer.stop()
        super().hide()

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.hide()
            self.closed.emit()
        super().keyPressEvent(event)


class TrayIcon(QSystemTrayIcon):
    """System tray icon with usage display."""

    refresh_requested = Signal()
    settings_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._popup = UsagePopup()
        self._usages: list[UsageData] = []

        # Set initial icon
        self._update_icon(None)

        # Context menu
        menu = QMenu()
        menu.setStyleSheet(
            "QMenu { background: #1e1e2e; color: #e0e0e0; border: 1px solid #333; }"
            "QMenu::item:selected { background: #333; }"
        )

        refresh_action = QAction("刷新", self)
        refresh_action.triggered.connect(self.refresh_requested.emit)
        menu.addAction(refresh_action)

        settings_action = QAction("设置", self)
        settings_action.triggered.connect(self.settings_requested.emit)
        menu.addAction(settings_action)

        menu.addSeparator()

        quit_action = QAction("退出", self)
        quit_action.triggered.connect(QApplication.quit)
        menu.addAction(quit_action)

        self.setContextMenu(menu)

        # Click handler
        self.activated.connect(self._on_activated)

        # Handle messageClicked (for Windows notification compatibility)
        self.messageClicked.connect(self._on_activated_fallback)

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            # Left click - show/toggle popup
            if self._popup.isVisible():
                self._popup.hide()
            else:
                self._popup.update_usage(self._usages)
                self._popup.show_at_tray()
            self.refresh_requested.emit()
        elif reason == QSystemTrayIcon.ActivationReason.Context:
            # Right click - context menu handled automatically
            pass
        elif reason == QSystemTrayIcon.ActivationReason.MiddleClick:
            self.refresh_requested.emit()

    def _on_activated_fallback(self) -> None:
        """Fallback activation handler."""
        if self._popup.isVisible():
            self._popup.hide()
        else:
            self._popup.update_usage(self._usages)
            self._popup.show_at_tray()

    def update_usage(self, usages: list[UsageData]) -> None:
        """Update the tray icon and popup with new usage data."""
        self._usages = usages

        # Only update popup content if it's visible
        if self._popup.isVisible():
            self._popup.update_usage(usages)

        # Calculate aggregate percentage for the tray icon
        percents = [
            u.windows[0].used_percent
            for u in usages
            if u.status == ProviderStatus.OK and u.windows
        ]
        avg = sum(percents) / len(percents) if percents else None
        self._update_icon(avg)

        # Update tooltip
        lines = []
        for u in usages:
            lines.append(f"{u.provider_name}: {u.summary_text}")
        self.setToolTip("\n".join(lines) if lines else "GlmBar - 暂无服务商")

    def _update_icon(self, percent: float | None) -> None:
        """Update the tray icon with current usage."""
        pixmap = create_usage_icon(percent)
        self.setIcon(QIcon(pixmap))

    def hide_popup(self) -> None:
        self._popup.hide()
