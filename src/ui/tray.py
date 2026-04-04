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
        self.setFixedHeight(10)
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
        if compact:
            self.setFrameShape(QFrame.Shape.NoFrame)
            self.setStyleSheet("background: transparent; border: none; padding: 0; margin: 0;")
            self._build_compact(usage)
        else:
            self.setFrameShape(QFrame.Shape.StyledPanel)
            self.setStyleSheet(
                "ProviderCard { background: #1e1e2e; border: 1px solid #333; "
                "border-radius: 8px; padding: 10px; }"
            )
            self._build(usage)

    @staticmethod
    def _pct_color(pct: float) -> str:
        if pct < 50:
            return "#4CAF50"
        elif pct < 80:
            return "#FFC107"
        return "#F44336"

    @staticmethod
    def _render_progress_bar(percent: float, width: int = 10) -> str:
        """Render a Unicode progress bar."""
        filled = round((percent / 100) * width)
        empty = width - filled
        return "█" * filled + "░" * empty

    def _build_compact(self, usage: UsageData) -> None:
        """Single QLabel with rich text — height is exactly the font height."""
        # 显示简短名称：智谱、百度等
        short_name = usage.provider_name.split('(')[0].split('（')[0].strip()
        parts = [f'<span style="color:#e0e0e0; font-weight:bold;">{short_name}：</span>']
        for i, w in enumerate(usage.windows):
            if i > 0:
                parts.append('<span style="color:#555;"> | </span>')
            short = w.label.replace("Token 配额", "Token").replace("MCP/时间配额", "MCP")
            c = self._pct_color(w.used_percent)
            parts.append(f'<span style="color:{c}; font-weight:bold;">{short}：{w.used_percent:.0f}%</span>')

        if not usage.windows:
            if usage.status == ProviderStatus.ERROR:
                parts.append('<span style="color:#F44336;">错误</span>')
            elif usage.status == ProviderStatus.UNAUTHORIZED:
                parts.append('<span style="color:#FF9800;">未授权</span>')

        if usage.balance is not None:
            parts.append(f'<span style="color:#4CAF50;"> ${usage.balance:.2f}</span>')

        label = QLabel("".join(parts))
        label.setStyleSheet("background: transparent; padding: 0; margin: 0; font-size: 12px;")
        label.setContentsMargins(0, 0, 0, 0)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(label)

    def _build(self, usage: UsageData) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(6)

        # Header: name + status
        header = QHBoxLayout()

        name_label = QLabel(usage.provider_name)
        name_label.setStyleSheet("color: #e0e0e0; font-size: 16px; font-weight: bold;")
        header.addWidget(name_label)

        header.addStretch()

        if usage.status != ProviderStatus.OK:
            status_text = usage.summary_text
            status_color = "#F44336" if usage.status == ProviderStatus.ERROR else (
                "#888" if usage.status == ProviderStatus.NO_API_KEY else "#FF9800"
            )
            status_label = QLabel(status_text)
            status_label.setStyleSheet(f"color: {status_color}; font-size: 13px;")
            header.addWidget(status_label)

        layout.addLayout(header)

        # Plan name
        if usage.plan_name:
            plan = QLabel(f"套餐: {usage.plan_name}")
            plan.setStyleSheet("color: #888; font-size: 13px;")
            layout.addWidget(plan)

        # Error message
        if usage.error_message:
            err = QLabel(usage.error_message)
            err.setStyleSheet("color: #FF9800; font-size: 13px;")
            err.setWordWrap(True)
            layout.addWidget(err)

        # Usage windows
        for w in usage.windows:
            win_layout = QVBoxLayout()
            win_layout.setSpacing(3)

            info = QHBoxLayout()
            lbl = QLabel(w.label)
            lbl.setStyleSheet("color: #aaa; font-size: 13px;")
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
            detail.setStyleSheet(f"color: {pct_color}; font-size: 13px; font-weight: bold;")
            info.addWidget(detail)

            win_layout.addLayout(info)

            bar = UsageBar()
            bar.set_percent(w.used_percent)
            win_layout.addWidget(bar)

            layout.addLayout(win_layout)

        # Balance (for credit-based providers)
        if usage.balance is not None:
            bal = QLabel(f"余额: ${usage.balance:.2f}")
            bal.setStyleSheet("color: #4CAF50; font-size: 13px;")
            layout.addWidget(bal)

        # Updated time
        time_str = usage.updated_at.strftime("%H:%M:%S")
        updated = QLabel(f"更新时间: {time_str}")
        updated.setStyleSheet("color: #555; font-size: 12px;")
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
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.NoDropShadowWindowHint,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        # Prevent window from appearing in taskbar during resize
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setWindowTitle("")  # Prevent Windows from showing class name as title
        self.setFixedWidth(380)
        self.setStyleSheet("background: transparent;")
        self._drag_pos = None
        self._drag_start = None
        self._dragging = False
        self._compact = False
        self._usages: list[UsageData] = []
        self._cards: list[ProviderCard] = []
        self._guide_frame: QFrame | None = None
        self._last_right_click_time: int = 0
        self._last_right_click_pos: QPoint = QPoint()

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
            "color: #e0e0e0; font-size: 18px; font-weight: bold; padding: 4px 0;"
        )
        self._layout.addWidget(self._title_label)

        # Two persistent pages — toggle only switches visibility,
        # no widget is destroyed or created during toggle ⇒ zero flicker.
        self._expanded_page = QWidget()
        self._expanded_page.setStyleSheet("background: transparent;")
        self._expanded_layout = QVBoxLayout(self._expanded_page)
        self._expanded_layout.setContentsMargins(0, 0, 0, 0)
        self._expanded_layout.setSpacing(8)
        self._layout.addWidget(self._expanded_page)

        self._compact_page = QWidget()
        self._compact_page.setStyleSheet("background: transparent;")
        self._compact_layout = QVBoxLayout(self._compact_page)
        self._compact_layout.setContentsMargins(0, 0, 0, 0)
        self._compact_layout.setSpacing(4)
        self._layout.addWidget(self._compact_page)
        self._compact_page.hide()  # start in expanded mode

        # Cards will be added directly to _expanded_page layout
        self._cards: list[ProviderCard] = []

        # Footer button bar
        self._footer = QWidget()
        self._footer.setStyleSheet("background: transparent;")
        footer_layout = QHBoxLayout(self._footer)
        footer_layout.setContentsMargins(0, 0, 0, 0)
        footer_layout.setSpacing(8)

        refresh_btn = QPushButton("刷新")
        refresh_btn.setStyleSheet(
            "QPushButton { background: #2a2a3a; color: #e0e0e0; border: 1px solid #444; "
            "border-radius: 6px; padding: 6px 16px; font-size: 12px; }"
            "QPushButton:hover { background: #3a3a4a; }"
        )
        refresh_btn.clicked.connect(self._on_refresh)

        settings_btn = QPushButton("设置")
        settings_btn.setStyleSheet(
            "QPushButton { background: #2a2a3a; color: #e0e0e0; border: 1px solid #444; "
            "border-radius: 6px; padding: 6px 16px; font-size: 12px; }"
            "QPushButton:hover { background: #3a3a4a; }"
        )
        settings_btn.clicked.connect(self.settings_requested.emit)

        footer_layout.addWidget(refresh_btn)
        footer_layout.addStretch()
        footer_layout.addWidget(settings_btn)
        self._layout.addWidget(self._footer)

        # Install event filter on all children so we can intercept drag
        self._install_drag_filter(self)

    def _install_drag_filter(self, widget: QWidget) -> None:
        """Recursively install drag event filter on all child widgets."""
        for child in widget.findChildren(QWidget):
            child.installEventFilter(self)

    def _handle_right_click(self, event) -> bool:
        """Detect right double-click manually via press timing.

        Returns True if a double-right-click was detected (and toggle fired).
        """
        import time

        now = int(time.monotonic() * 1000)
        pos = event.globalPosition().toPoint()
        interval = QApplication.doubleClickInterval()

        if (
            now - self._last_right_click_time < interval
            and (pos - self._last_right_click_pos).manhattanLength() < 8
        ):
            self._toggle_compact()
            self._last_right_click_time = 0
            return True

        self._last_right_click_time = now
        self._last_right_click_pos = pos
        return False

    def eventFilter(self, obj, event) -> bool:
        """Forward drag (left) and double-click (right) from children to this window."""
        from PySide6.QtCore import QEvent

        # Right double-click: catch Qt's built-in DblClick (same-widget) ...
        if event.type() == QEvent.Type.MouseButtonDblClick:
            if event.button() == Qt.MouseButton.RightButton:
                self._last_right_click_time = 0  # prevent manual re-trigger
                self._toggle_compact()
                return True

        # ... and also track Press for cross-widget manual detection
        if event.type() == QEvent.Type.MouseButtonPress:
            if event.button() == Qt.MouseButton.RightButton:
                self._handle_right_click(event)
                return True  # consume right-clicks to prevent context menu
            if event.button() == Qt.MouseButton.LeftButton:
                self.mousePressEvent(event)
                return False

        if event.type() == QEvent.Type.MouseMove:
            if hasattr(event, "buttons") and event.buttons() & Qt.MouseButton.LeftButton:
                self.mouseMoveEvent(event)
                return False

        if event.type() == QEvent.Type.MouseButtonRelease:
            if event.button() == Qt.MouseButton.LeftButton:
                self.mouseReleaseEvent(event)
                return False

        return super().eventFilter(obj, event)

    @staticmethod
    def _clear_layout(layout) -> None:
        """Remove and schedule deletion of all items in a layout."""
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
            sub = item.layout()
            if sub is not None:
                UsagePopup._clear_layout(sub)

    def update_usage(self, usages: list[UsageData]) -> None:
        """Update the display with new usage data.

        Builds content into BOTH pages so that _toggle_compact can
        switch pages instantly without rebuilding anything.
        """
        self._usages = usages
        active_usages = [u for u in usages if u.status != ProviderStatus.NO_API_KEY]

        # ---- Rebuild expanded page ----
        self._clear_layout(self._expanded_layout)
        self._cards.clear()
        self._guide_frame = None

        if not active_usages:
            # No API keys → show setup guide
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

            self._guide_frame = guide
            self._expanded_layout.addWidget(guide)
        else:
            for usage in active_usages:
                card = ProviderCard(usage, compact=False)
                card.show()
                self._cards.append(card)
                self._expanded_layout.addWidget(card)

        # ---- Rebuild compact page ----
        self._clear_layout(self._compact_layout)

        if active_usages:
            name_width = 65

            for usage in active_usages:
                short_name = usage.provider_name.split('(')[0].split('（')[0].strip()

                provider_row = QWidget()
                provider_row.setStyleSheet("background: transparent;")
                row_layout = QHBoxLayout(provider_row)
                row_layout.setContentsMargins(0, 0, 0, 0)
                row_layout.setSpacing(4)

                # Left: platform name block
                name_box = QFrame()
                name_box.setStyleSheet(
                    "QFrame { background: #1e1e2e; border: 1px solid #333; border-radius: 4px; }"
                )
                name_box.setFixedWidth(name_width)
                name_layout = QVBoxLayout(name_box)
                name_layout.setContentsMargins(4, 4, 4, 4)
                name_layout.setSpacing(2)

                name_layout.addStretch()
                name_label = QLabel(short_name)
                name_label.setStyleSheet("color: #e0e0e0; font-size: 11px; font-weight: bold;")
                name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                name_layout.addWidget(name_label)
                name_layout.addStretch()

                name_box.setMinimumHeight(0)
                row_layout.addWidget(name_box)

                # Right: quota list
                quota_container = QWidget()
                quota_container.setStyleSheet("background: transparent;")
                quota_layout = QVBoxLayout(quota_container)
                quota_layout.setContentsMargins(0, 0, 0, 0)
                quota_layout.setSpacing(2)

                if not usage.windows:
                    error_label = QLabel("无数据" if usage.status == ProviderStatus.OK else ("错误" if usage.status == ProviderStatus.ERROR else "未授权"))
                    error_color = "#888" if usage.status == ProviderStatus.OK else ("#F44336" if usage.status == ProviderStatus.ERROR else "#FF9800")
                    error_label.setStyleSheet(f"color: {error_color}; font-size: 12px;")
                    quota_layout.addWidget(error_label)
                else:
                    for w in usage.windows:
                        label = w.label
                        if "Token" in label:
                            label = "Token"
                        elif "5小时" in label or "5Hour" in label.lower():
                            label = "5小时"
                        elif "每周" in label or "week" in label.lower():
                            label = "每周"
                        elif "每月" in label or "month" in label.lower():
                            label = "每月"
                        elif "MCP" in label or "时间" in label:
                            label = "MCP"

                        c = ProviderCard._pct_color(w.used_percent)

                        quota_row = QHBoxLayout()
                        quota_row.setContentsMargins(0, 0, 0, 0)
                        quota_row.setSpacing(4)

                        label_widget = QLabel(label)
                        label_widget.setFixedWidth(40)
                        label_widget.setStyleSheet("color: #888; font-size: 11px;")
                        quota_row.addWidget(label_widget)

                        bar_widget = UsageBar()
                        bar_widget.setFixedHeight(10)
                        bar_widget.setFixedWidth(80)
                        bar_widget.set_percent(w.used_percent)
                        quota_row.addWidget(bar_widget)

                        pct_label = QLabel(f"{w.used_percent:.0f}%")
                        pct_label.setStyleSheet(f"color: {c}; font-size: 11px; font-weight: bold;")
                        pct_label.setFixedWidth(32)
                        quota_row.addWidget(pct_label)

                        quota_layout.addLayout(quota_row)

                row_layout.addWidget(quota_container)

                quota_container.adjustSize()
                name_box.setMinimumHeight(quota_container.sizeHint().height())

                self._compact_layout.addWidget(provider_row)

        # ---- Show the correct page ----
        if self._compact:
            self._expanded_page.hide()
            self._compact_page.show()
        else:
            self._compact_page.hide()
            self._expanded_page.show()

        self._install_drag_filter(self)
        self._apply_window_size()

    def _apply_window_size(self) -> None:
        """Apply the correct window size based on current mode."""
        self.setMinimumSize(0, 0)
        self.setMaximumSize(16777215, 16777215)
        self._container.updateGeometry()

        if self._compact:
            # Compact mode: shrink to fit content
            self._container.adjustSize()
            size = self._container.size()
            self.setFixedSize(size.width() + 2, size.height() + 2)
        else:
            # Expanded mode: fixed width, auto height
            self.setFixedWidth(420)
            self.adjustSize()

    def _toggle_compact(self) -> None:
        """Toggle between compact and expanded mode.

        Only switches page visibility — no widget creation or destruction.
        No hide/show/move tricks needed because we never destroy widgets.
        """
        self._compact = not self._compact
        if self._compact:
            self._title_label.hide()
            self._footer.hide()
            self._container.setStyleSheet(
                "QFrame { background: #12121e; border: 1px solid #333; "
                "border-radius: 6px; }"
            )
            self._layout.setContentsMargins(8, 4, 8, 4)
            self._expanded_page.hide()
            self._compact_page.show()
        else:
            self._title_label.show()
            self._footer.show()
            self._container.setStyleSheet(
                "QFrame { background: #12121e; border: 1px solid #333; "
                "border-radius: 12px; }"
            )
            self._layout.setContentsMargins(16, 12, 16, 12)
            self._compact_page.hide()
            self._expanded_page.show()

        self._apply_window_size()

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
        """Handle right double-click detection and start potential left-drag."""
        if event.button() == Qt.MouseButton.RightButton:
            self._handle_right_click(event)
            return
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start = event.globalPosition().toPoint()
            self._drag_pos = event.globalPosition().toPoint() - self.pos()
            self._dragging = False
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        """Move the popup while dragging (only after 4px threshold)."""
        if self._drag_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:
            if not self._dragging and self._drag_start is not None:
                delta = event.globalPosition().toPoint() - self._drag_start
                if delta.manhattanLength() < 4:
                    return
            self._dragging = True
            self.move(event.globalPosition().toPoint() - self._drag_pos)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        """Stop dragging."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = None
            self._drag_start = None
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        """Right-double-click toggles between compact and expanded mode."""
        if event.button() == Qt.MouseButton.RightButton:
            self._last_right_click_time = 0  # prevent manual re-trigger
            self._toggle_compact()
        super().mouseDoubleClickEvent(event)

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
