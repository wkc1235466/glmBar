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
    QPushButton,
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

    def __init__(self, usage: UsageData, compact: bool = False, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        if compact:
            self.setStyleSheet(
                "ProviderCard { background: #1e1e2e; border: 1px solid #333; "
                "border-radius: 6px; padding: 4px 8px; }"
            )
        else:
            self.setStyleSheet(
                "ProviderCard { background: #1e1e2e; border: 1px solid #333; "
                "border-radius: 8px; padding: 8px; }"
            )
        if compact:
            self._build_compact(usage)
        else:
            self._build(usage)

    def _build_compact(self, usage: UsageData) -> None:
        """Build a single-line compact layout showing all windows."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(4)

        # Provider/plan name
        name_text = usage.plan_name if usage.plan_name else usage.provider_name
        name = QLabel(name_text)
        name.setStyleSheet("color: #e0e0e0; font-size: 12px; font-weight: bold;")
        layout.addWidget(name)

        # All windows in one line
        for i, w in enumerate(usage.windows):
            sep = QLabel("|")
            sep.setStyleSheet("color: #444; font-size: 11px;")
            layout.addWidget(sep)

            short = w.label.replace("Token 配额", "Tokens").replace("MCP/时间配额", "MCP")
            pct_color = (
                "#4CAF50" if w.used_percent < 50
                else "#FFC107" if w.used_percent < 80
                else "#F44336"
            )
            info = QLabel(f"{short}: {w.used_percent:.0f}%")
            info.setStyleSheet(f"color: {pct_color}; font-size: 11px; font-weight: bold;")
            layout.addWidget(info)

            # Reset time on first window only
            if i == 0 and w.resets_at:
                delta = w.resets_at - datetime.now(timezone.utc)
                if delta.total_seconds() > 0:
                    hours = int(delta.total_seconds() // 3600)
                    mins = int((delta.total_seconds() % 3600) // 60)
                    reset_text = f"({hours}时{mins}分)" if hours > 0 else f"({mins}分)"
                    reset = QLabel(reset_text)
                    reset.setStyleSheet("color: #555; font-size: 10px;")
                    layout.addWidget(reset)

        if not usage.windows:
            if usage.status == ProviderStatus.ERROR:
                err = QLabel("错误")
                err.setStyleSheet("color: #F44336; font-size: 12px;")
                layout.addWidget(err)
            elif usage.status == ProviderStatus.UNAUTHORIZED:
                err = QLabel("未授权")
                err.setStyleSheet("color: #FF9800; font-size: 12px;")
                layout.addWidget(err)

        layout.addStretch()

        # Balance
        if usage.balance is not None:
            bal = QLabel(f"${usage.balance:.2f}")
            bal.setStyleSheet("color: #4CAF50; font-size: 11px;")
            layout.addWidget(bal)

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

        if usage.status != ProviderStatus.OK:
            status_text = usage.summary_text
            status_color = "#F44336" if usage.status == ProviderStatus.ERROR else (
                "#888" if usage.status == ProviderStatus.NO_API_KEY else "#FF9800"
            )
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

            detail_parts = [f"{w.used_percent:.0f}%"]
            if w.resets_at:
                from datetime import timezone
                delta = w.resets_at - datetime.now(timezone.utc)
                if delta.total_seconds() > 0:
                    hours = int(delta.total_seconds() // 3600)
                    mins = int((delta.total_seconds() % 3600) // 60)
                    detail_parts.append(f"{hours}时{mins}分后重置")

            pct_color = (
                "#4CAF50" if w.used_percent < 50
                else "#FFC107" if w.used_percent < 80
                else "#F44336"
            )
            detail = QLabel("  ".join(detail_parts))
            detail.setStyleSheet(f"color: {pct_color}; font-size: 11px; font-weight: bold;")
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

    Uses Qt.Window + stays-on-top for a persistent, draggable panel.
    Child widgets forward mouse drag events to this top-level window.
    """

    closed = Signal()
    settings_requested = Signal()
    refresh_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(
            parent,
            Qt.WindowType.Window
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedWidth(380)
        self.setStyleSheet("background: transparent;")
        self._drag_pos = None
        self._dragging = False
        self._compact = False
        self._usages: list[UsageData] = []

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

        # Title bar area — visual only, dragging handled via event filter
        self._title_label = QLabel("GlmBar - 编程套餐用量")
        self._title_label.setStyleSheet(
            "color: #e0e0e0; font-size: 16px; font-weight: bold; padding: 4px 0;"
        )
        self._layout.addWidget(self._title_label)

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

        # Footer button bar
        footer_layout = QHBoxLayout()
        footer_layout.setSpacing(8)

        refresh_btn = QPushButton("刷新")
        refresh_btn.setStyleSheet(
            "QPushButton { background: #2a2a3a; color: #e0e0e0; border: 1px solid #444; "
            "border-radius: 6px; padding: 6px 16px; font-size: 12px; }"
            "QPushButton:hover { background: #3a3a4a; }"
        )
        refresh_btn.clicked.connect(self._on_refresh)

        self._compact_btn = QPushButton("迷你")
        self._compact_btn.setStyleSheet(
            "QPushButton { background: #2a2a3a; color: #e0e0e0; border: 1px solid #444; "
            "border-radius: 6px; padding: 6px 16px; font-size: 12px; }"
            "QPushButton:hover { background: #3a3a4a; }"
        )
        self._compact_btn.clicked.connect(self._toggle_compact)

        settings_btn = QPushButton("设置")
        settings_btn.setStyleSheet(
            "QPushButton { background: #2a2a3a; color: #e0e0e0; border: 1px solid #444; "
            "border-radius: 6px; padding: 6px 16px; font-size: 12px; }"
            "QPushButton:hover { background: #3a3a4a; }"
        )
        settings_btn.clicked.connect(self.settings_requested.emit)

        footer_layout.addWidget(refresh_btn)
        footer_layout.addWidget(self._compact_btn)
        footer_layout.addStretch()
        footer_layout.addWidget(settings_btn)
        self._layout.addLayout(footer_layout)

        # Install event filter on all children so we can intercept drag
        self._install_drag_filter(self)

    def _install_drag_filter(self, widget: QWidget) -> None:
        """Recursively install drag event filter on all child widgets."""
        for child in widget.findChildren(QWidget):
            child.installEventFilter(self)

    def eventFilter(self, obj, event) -> bool:
        """Forward left-button drag from any child to this window."""
        from PySide6.QtCore import QEvent

        if event.type() in (
            QEvent.Type.MouseButtonPress,
            QEvent.Type.MouseMove,
            QEvent.Type.MouseButtonRelease,
        ):
            if event.button() == Qt.MouseButton.LeftButton or (
                hasattr(event, "buttons") and event.buttons() & Qt.MouseButton.LeftButton
            ):
                # Deliver to self's handlers
                if event.type() == QEvent.Type.MouseButtonPress:
                    self.mousePressEvent(event)
                elif event.type() == QEvent.Type.MouseMove:
                    self.mouseMoveEvent(event)
                elif event.type() == QEvent.Type.MouseButtonRelease:
                    self.mouseReleaseEvent(event)
                return False  # let the child also process it (e.g. scroll)
        return super().eventFilter(obj, event)

    def update_usage(self, usages: list[UsageData]) -> None:
        """Update the display with new usage data.

        Only shows providers that have an API key configured.
        When no keys are configured, displays a setup guide card.
        """
        self._usages = usages

        # Filter out providers without API keys
        active_usages = [u for u in usages if u.status != ProviderStatus.NO_API_KEY]

        # Clear existing cards
        while self._cards_layout.count():
            item = self._cards_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not active_usages:
            # Show setup guide card
            guide = QFrame()
            guide.setStyleSheet(
                "QFrame { background: #1e1e2e; border: 1px solid #333; "
                "border-radius: 8px; padding: 16px; }"
            )
            guide_layout = QVBoxLayout(guide)
            guide_layout.setContentsMargins(16, 16, 16, 16)
            guide_layout.setSpacing(12)

            hint = QLabel("请先在设置中配置您的 API 密钥")
            hint.setStyleSheet("color: #888; font-size: 13px;")
            hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
            hint.setWordWrap(True)
            guide_layout.addWidget(hint)

            open_btn = QPushButton("打开设置")
            open_btn.setStyleSheet(
                "QPushButton { background: #4CAF50; color: white; border: none; "
                "border-radius: 6px; padding: 8px 24px; font-size: 13px; font-weight: bold; }"
                "QPushButton:hover { background: #45a049; }"
            )
            open_btn.clicked.connect(self.settings_requested.emit)
            guide_layout.addWidget(open_btn, alignment=Qt.AlignmentFlag.AlignCenter)

            self._cards_layout.addWidget(guide)
        else:
            for usage in active_usages:
                card = ProviderCard(usage, compact=self._compact)
                self._cards_layout.addWidget(card)

        self._cards_layout.addStretch()
        self._cards_widget.adjustSize()
        self.adjustSize()

    def _toggle_compact(self) -> None:
        """Toggle between compact and expanded mode."""
        self._compact = not self._compact
        self._compact_btn.setText("展开" if self._compact else "迷你")
        self.setFixedWidth(420 if self._compact else 380)
        self.update_usage(self._usages)

    def _on_refresh(self) -> None:
        """Emit refresh signal (TrayIcon connects to this)."""
        self.refresh_requested.emit()

    def show_at_tray(self) -> None:
        """Show the popup positioned near the system tray."""
        screen = QApplication.primaryScreen().geometry()
        w = self.sizeHint().width()
        h = self.sizeHint().height()
        x = screen.right() - w - 16
        y = screen.bottom() - h - 60

        self.move(x, y)
        self.show()
        self.raise_()

    def mousePressEvent(self, event) -> None:
        """Start dragging."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.pos()
            self._dragging = False
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        """Move the popup while dragging."""
        if self._drag_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self._dragging = True
            self.move(event.globalPosition().toPoint() - self._drag_pos)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        """Stop dragging."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = None
        super().mouseReleaseEvent(event)

    def hide(self) -> None:
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
        self._popup.settings_requested.connect(self.settings_requested.emit)
        self._popup.refresh_requested.connect(self.refresh_requested.emit)
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

        # Calculate aggregate percentage for the tray icon (only providers with keys)
        active_usages = [u for u in usages if u.status != ProviderStatus.NO_API_KEY]
        percents = [
            u.windows[0].used_percent
            for u in active_usages
            if u.status == ProviderStatus.OK and u.windows
        ]
        avg = sum(percents) / len(percents) if percents else None
        self._update_icon(avg)

        # Update tooltip (only providers with keys)
        lines = []
        for u in active_usages:
            lines.append(f"{u.provider_name}: {u.summary_text}")
        self.setToolTip("\n".join(lines) if lines else "GlmBar - 请配置 API 密钥")

    def _update_icon(self, percent: float | None) -> None:
        """Update the tray icon with current usage."""
        pixmap = create_usage_icon(percent)
        self.setIcon(QIcon(pixmap))

    def hide_popup(self) -> None:
        self._popup.hide()
