"""Settings window for managing providers and API keys."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal, QUrl
from PySide6.QtGui import QFont, QDesktopServices
from PySide6.QtWidgets import (
    QSizePolicy,
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from src.config.settings import (
    AppConfig,
    ProviderConfig,
    PROVIDER_DISPLAY_NAMES,
    PROVIDER_SHORT_NAMES,
    save_config,
)
from src.providers.registry import provider_registry


_SETTINGS_BASE_STYLESHEET = (
    "QDialog { background: #1e1e2e; color: #e0e0e0; }"
    "QLabel { color: #ccc; font-size: 12px; }"
    "QPushButton { background: #6C63FF; color: white; border: none; "
    "border-radius: 6px; padding: 8px 16px; font-size: 13px; }"
    "QPushButton:hover { background: #5a52e0; }"
    "QPushButton#secondary, QPushButton#cancel { background: #444; }"
    "QPushButton#secondary:hover, QPushButton#cancel:hover { background: #555; }"
    "QLineEdit { background: #2a2a3a; color: #e0e0e0; border: 1px solid #444; "
    "border-radius: 4px; padding: 6px; }"
    "QLineEdit:focus { border-color: #6C63FF; }"
    "QComboBox { background: #2a2a3a; color: #e0e0e0; border: 1px solid #444; "
    "border-radius: 4px; padding: 6px; }"
    "QComboBox QAbstractItemView { background: #2a2a3a; color: #e0e0e0; "
    "selection-background-color: #444; }"
)


class ProviderEditDialog(QDialog):
    """Dialog for editing a single provider's configuration."""

    def __init__(self, config: ProviderConfig | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("添加服务商" if config is None else "编辑服务商")
        self.setMinimumWidth(420)
        self.setStyleSheet(_SETTINGS_BASE_STYLESHEET)
        self._config = config
        self._fields: dict[str, QWidget] = {}
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Provider type selector
        type_label = QLabel("服务商类型")
        layout.addWidget(type_label)

        self._type_combo = QComboBox()
        for type_id, cls in provider_registry.available_types.items():
            name = PROVIDER_DISPLAY_NAMES.get(type_id, cls.__name__.replace("Provider", ""))
            self._type_combo.addItem(name, type_id)

        self._type_combo.addItem("自定义 (custom)", "custom")
        self._type_combo.currentIndexChanged.connect(self._on_type_changed)
        layout.addWidget(self._type_combo)

        # Dynamic fields container
        self._fields_container = QWidget()
        self._fields_layout = QVBoxLayout(self._fields_container)
        self._fields_layout.setSpacing(8)
        self._fields_layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._fields_container)

        # Custom provider fields
        self._custom_container = QWidget()
        custom_layout = QVBoxLayout(self._custom_container)
        custom_layout.setSpacing(8)
        custom_layout.setContentsMargins(0, 0, 0, 0)

        self._custom_id = QLineEdit()
        self._custom_id.setPlaceholderText("例如 deepseek")
        custom_layout.addWidget(QLabel("服务商 ID"))
        custom_layout.addWidget(self._custom_id)

        self._custom_name = QLineEdit()
        self._custom_name.setPlaceholderText("例如 DeepSeek")
        custom_layout.addWidget(QLabel("显示名称"))
        custom_layout.addWidget(self._custom_name)

        self._custom_url = QLineEdit()
        self._custom_url.setPlaceholderText("https://api.example.com/usage")
        custom_layout.addWidget(QLabel("配额查询 URL"))
        custom_layout.addWidget(self._custom_url)

        self._custom_env_key = QLineEdit()
        self._custom_env_key.setPlaceholderText("例如 DEEPSEEK_API_KEY")
        custom_layout.addWidget(QLabel("环境变量名（可选）"))
        custom_layout.addWidget(self._custom_env_key)

        self._custom_container.hide()
        layout.addWidget(self._custom_container)

        # Buttons
        btn_layout = QHBoxLayout()
        cancel_btn = QPushButton("取消")
        cancel_btn.setObjectName("cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addStretch()
        btn_layout.addWidget(cancel_btn)

        save_btn = QPushButton("保存")
        save_btn.clicked.connect(self._on_save)
        btn_layout.addWidget(save_btn)
        layout.addLayout(btn_layout)

        # Pre-fill if editing
        if self._config:
            self._prefill()

    def _on_type_changed(self) -> None:
        """Rebuild dynamic fields when provider type changes."""
        # Clear old fields
        while self._fields_layout.count():
            item = self._fields_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._fields.clear()

        type_id = self._type_combo.currentData()
        is_custom = type_id == "custom"
        self._custom_container.setVisible(is_custom)

        if is_custom:
            return

        cls = provider_registry.get_type(type_id)
        if not cls:
            return

        # Create a temp instance to get display config
        temp = cls.__new__(cls)
        temp.__init__(api_key="")
        config_fields = temp.get_display_config()

        for field_name, field_type in config_fields.items():
            label_text = field_name.replace("_", " ").title()
            if field_type == "password":
                label_text = "API 密钥"
            elif field_type == "textarea":
                label_text = "curl 命令"
            label = QLabel(label_text)
            self._fields_layout.addWidget(label)

            if field_type.startswith("select:"):
                options = field_type.split(":", 1)[1].split(",")
                combo = QComboBox()
                region_labels = {"china": "国内", "global": "国际"}
                for opt in options:
                    opt_label = region_labels.get(opt, opt)
                    combo.addItem(opt_label, opt)
                self._fields[field_name] = combo
                self._fields_layout.addWidget(combo)
            elif field_type == "textarea":
                text_edit = QTextEdit()
                text_edit.setMaximumHeight(120)
                text_edit.setPlaceholderText("粘贴 resourceList 请求的 curl 命令（复制为 cURL(bash)）...")
                text_edit.setStyleSheet(
                    "QTextEdit { background: #2a2a3a; color: #e0e0e0; border: 1px solid #444; "
                    "border-radius: 4px; padding: 6px; font-family: monospace; font-size: 11px; }"
                    "QTextEdit:focus { border-color: #6C63FF; }"
                )
                self._fields[field_name] = text_edit
                self._fields_layout.addWidget(text_edit)

                # 百度千帆：添加教程链接
                if type_id == "baidu":
                    help_btn = QPushButton("如何获取 curl 命令？")
                    help_btn.setObjectName("secondary")
                    help_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                    help_btn.setSizePolicy(
                        QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed
                    )
                    help_btn.clicked.connect(self._show_baidu_tutorial)
                    self._fields_layout.addWidget(help_btn)
            else:
                line_edit = QLineEdit()
                if field_type == "password":
                    line_edit.setEchoMode(QLineEdit.EchoMode.Password)
                    line_edit.setPlaceholderText("请输入 API 密钥...")
                self._fields[field_name] = line_edit
                self._fields_layout.addWidget(line_edit)

    def _prefill(self) -> None:
        """Fill form with existing config values."""
        cfg = self._config
        # Find type in combo
        for i in range(self._type_combo.count()):
            if self._type_combo.itemData(i) == cfg.type:
                self._type_combo.setCurrentIndex(i)
                break

        if cfg.type == "custom":
            self._custom_id.setText(cfg.id)
            self._custom_name.setText(cfg.name)
            self._custom_url.setText(cfg.extra.get("quota_url", ""))
            self._custom_env_key.setText(cfg.extra.get("env_key", ""))
        elif cfg.type == "baidu":
            # 百度千帆：显示已配置状态提示，不回填 curl
            curl_widget = self._fields.get("curl")
            if curl_widget and isinstance(curl_widget, QTextEdit):
                has_config = cfg.extra.get("cookie") or cfg.extra.get("csrftoken")
                if has_config:
                    curl_widget.setPlaceholderText(
                        "已有配置。如需更新，粘贴新的 curl 命令覆盖即可。"
                    )
        else:
            # Fill dynamic fields from extra config
            for name, widget in self._fields.items():
                val = cfg.extra.get(name)
                if val is None and name == "api_key":
                    val = cfg.api_key
                if val is not None:
                    if isinstance(widget, QComboBox):
                        idx = widget.findData(val)
                        if idx >= 0:
                            widget.setCurrentIndex(idx)
                    elif isinstance(widget, QTextEdit):
                        widget.setText(str(val))
                    else:
                        widget.setText(str(val))

    def _show_baidu_tutorial(self) -> None:
        """显示百度千帆 curl 获取教程对话框。"""
        tutorial_text = (
            "<div style='color:#e0e0e0; font-size:13px; line-height:1.8;'>"
            "<h3 style='color:#6C63FF;'>获取 curl 命令步骤</h3>"
            "<p><b style='color:#fff;'>1.</b> 登录 "
            "<a href='https://console.bce.baidu.com/qianfan/resource/subscribe' "
            "style='color:#6C63FF;'>百度千帆资源订阅页面</a></p>"
            "<p><b style='color:#fff;'>2.</b> 按 <b>F12</b> 打开浏览器开发者工具，"
            "切换到 <b>网络 (Network)</b> 标签页</p>"
            "<p><b style='color:#fff;'>3.</b> 在网络请求列表中找到名为 "
            "<b style='color:#FFD700;'>resourceList</b> 的请求</p>"
            "<p><b style='color:#fff;'>4.</b> 右键点击该请求 → <b>复制</b> → "
            "<b>复制为 cURL(bash)</b>"
            "（注意：选\"复制为 cURL(bash)\"，不要选\"全部复制\"）</p>"
            "<p><b style='color:#fff;'>5.</b> 将复制的内容粘贴到上方的文本框中，"
            "点击保存即可</p>"
            "</div>"
        )
        dlg = QMessageBox(self)
        dlg.setWindowTitle("获取 curl 命令教程")
        dlg.setTextFormat(Qt.TextFormat.RichText)
        dlg.setText(tutorial_text)
        dlg.setStyleSheet(
            "QMessageBox { background: #1e1e2e; }"
            "QMessageBox QLabel { color: #e0e0e0; min-width: 420px; }"
            "QPushButton { background: #6C63FF; color: white; border: none; "
            "border-radius: 6px; padding: 8px 24px; font-size: 13px; }"
            "QPushButton:hover { background: #5a52e0; }"
        )
        # 让链接可点击
        dlg.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextBrowserInteraction
        )
        dlg.exec()

    def _on_save(self) -> None:
        type_id = self._type_combo.currentData()

        if type_id == "custom":
            pid = self._custom_id.text().strip()
            name = self._custom_name.text().strip()
            if not pid or not name:
                QMessageBox.warning(self, "验证失败", "服务商 ID 和名称为必填项。")
                return
            extra = {"quota_url": self._custom_url.text().strip()}
            env_key = self._custom_env_key.text().strip()
            if env_key:
                extra["env_key"] = env_key
            self.result_config = ProviderConfig(
                id=pid,
                type="custom",
                name=name,
                api_key="",
                extra=extra,
            )
        else:
            api_key = ""
            extra: dict[str, Any] = {}
            # 百度千帆特殊处理：解析 curl 文本
            if type_id == "baidu":
                curl_widget = self._fields.get("curl")
                curl_text = ""
                if curl_widget and isinstance(curl_widget, QTextEdit):
                    curl_text = curl_widget.toPlainText().strip()
                if curl_text:
                    from src.providers.baidu import BaiduQianfanProvider

                    parsed = BaiduQianfanProvider.parse_curl(curl_text)
                    if not parsed.get("cookie"):
                        QMessageBox.warning(
                            self,
                            "解析失败",
                            "无法从 curl 命令中提取 Cookie 信息，请确保复制了正确的请求。",
                        )
                        return
                    extra.update(parsed)
                elif self._config:
                    # Re-editing without new curl: preserve existing auth data
                    for k in ("cookie", "csrftoken", "x-bce-jt"):
                        v = self._config.extra.get(k)
                        if v:
                            extra[k] = v
            else:
                for name, widget in self._fields.items():
                    if isinstance(widget, QComboBox):
                        extra[name] = widget.currentData()
                    elif isinstance(widget, QTextEdit):
                        extra[name] = widget.toPlainText().strip()
                    elif name == "api_key":
                        api_key = widget.text().strip()
                    else:
                        extra[name] = widget.text().strip()

            # Get default name from type
            cls = provider_registry.get_type(type_id)
            temp = cls.__new__(cls)
            temp.__init__(api_key="")
            default_name = temp.name

            pid = self._config.id if self._config else type_id
            name = self._config.name if self._config else default_name

            self.result_config = ProviderConfig(
                id=pid,
                type=type_id,
                name=name,
                api_key=api_key,
                extra=extra,
            )

        self.accept()

    def get_config(self) -> ProviderConfig | None:
        return getattr(self, "result_config", None)


class SettingsWindow(QDialog):
    """Main settings window."""

    config_changed = Signal()

    def __init__(self, config: AppConfig, parent=None):
        super().__init__(parent)
        self.setWindowTitle("GlmBar 设置")
        self.setMinimumSize(550, 450)
        self._config = config
        self.setStyleSheet(_SETTINGS_BASE_STYLESHEET + (
            "QPushButton#danger { background: #c0392b; }"
            "QPushButton#danger:hover { background: #e74c3c; }"
            "QSpinBox { background: #2a2a3a; color: #e0e0e0; border: 1px solid #444; "
            "border-radius: 4px; padding: 4px; }"
            "QTableWidget { background: #1a1a2a; color: #e0e0e0; border: 1px solid #333; "
            "gridline-color: #333; }"
            "QTableWidget::item { padding: 6px; }"
            "QTableWidget::item:selected { background: #333; }"
            "QHeaderView::section { background: #252535; color: #ccc; "
            "border: 1px solid #333; padding: 6px; font-weight: bold; }"
            "QCheckBox { color: #ccc; }"
            "QCheckBox::indicator { width: 16px; height: 16px; }"
        ))
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        # General settings
        gen_label = QLabel("通用设置")
        gen_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #e0e0e0;")
        layout.addWidget(gen_label)

        refresh_layout = QHBoxLayout()
        refresh_layout.addWidget(QLabel("刷新间隔（秒）："))
        self._refresh_spin = QSpinBox()
        self._refresh_spin.setRange(10, 600)
        self._refresh_spin.setValue(self._config.refresh_interval_seconds)
        self._refresh_spin.setSuffix("s")
        refresh_layout.addWidget(self._refresh_spin)
        refresh_layout.addStretch()
        layout.addLayout(refresh_layout)

        # Providers
        prov_label = QLabel("服务商列表")
        prov_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #e0e0e0;")
        layout.addWidget(prov_label)

        # Provider table
        self._table = QTableWidget()
        self._table.setColumnCount(4)
        self._table.setHorizontalHeaderLabels(["启用", "服务商", "类型", "API 密钥"])
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self._table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self._table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.ResizeToContents
        )
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._populate_table()
        layout.addWidget(self._table)

        # Buttons
        btn_layout = QHBoxLayout()

        add_btn = QPushButton("添加服务商")
        add_btn.clicked.connect(self._add_provider)
        btn_layout.addWidget(add_btn)

        edit_btn = QPushButton("编辑")
        edit_btn.setObjectName("secondary")
        edit_btn.clicked.connect(self._edit_provider)
        btn_layout.addWidget(edit_btn)

        del_btn = QPushButton("移除")
        del_btn.setObjectName("danger")
        del_btn.clicked.connect(self._remove_provider)
        btn_layout.addWidget(del_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # Save / Close
        footer = QHBoxLayout()
        footer.addStretch()
        close_btn = QPushButton("关闭")
        close_btn.setObjectName("secondary")
        close_btn.clicked.connect(self._save_and_close)
        footer.addWidget(close_btn)
        layout.addLayout(footer)

    def _populate_table(self) -> None:
        self._table.setRowCount(len(self._config.providers))
        for row, prov in enumerate(self._config.providers):
            # Enabled
            from PySide6.QtWidgets import QCheckBox
            cb = QCheckBox()
            cb.setChecked(prov.enabled)
            cb.setStyleSheet("QCheckBox { color: #ccc; }")
            self._table.setCellWidget(row, 0, cb)

            # Name
            name_item = QTableWidgetItem(prov.name)
            name_item.setForeground(Qt.GlobalColor.white)
            self._table.setItem(row, 1, name_item)

            # Type
            type_item = QTableWidgetItem(PROVIDER_SHORT_NAMES.get(prov.type, prov.type))
            type_item.setForeground(Qt.GlobalColor.gray)
            self._table.setItem(row, 2, type_item)

            # API Key (masked)
            key = prov.api_key
            if len(key) > 12:
                masked = f"{key[:8]}...{key[-4:]}"
            elif key:
                masked = "已设置"
            elif prov.type == "baidu" and (
                prov.extra.get("cookie") or prov.extra.get("csrftoken")
            ):
                masked = "已配置"
            else:
                masked = "未设置"
            key_item = QTableWidgetItem(masked)
            is_configured = bool(key) or masked == "已配置"
            key_item.setForeground(
                Qt.GlobalColor.green if is_configured else Qt.GlobalColor.gray
            )
            self._table.setItem(row, 3, key_item)

    def _get_selected_row(self) -> int:
        rows = self._table.selectionModel().selectedRows()
        return rows[0].row() if rows else -1

    def _add_provider(self) -> None:
        dlg = ProviderEditDialog(parent=self)
        dlg._on_type_changed()  # Build initial fields
        if dlg.exec() == QDialog.DialogCode.Accepted:
            cfg = dlg.get_config()
            if cfg:
                self._config.providers.append(cfg)
                self._populate_table()
                self.config_changed.emit()

    def _edit_provider(self) -> None:
        row = self._get_selected_row()
        if row < 0:
            return
        prov = self._config.providers[row]
        dlg = ProviderEditDialog(config=prov, parent=self)
        # _prefill() inside _build() already sets type and fills fields
        if dlg.exec() == QDialog.DialogCode.Accepted:
            new_cfg = dlg.get_config()
            if new_cfg:
                self._config.providers[row] = new_cfg
                self._populate_table()
                self.config_changed.emit()

    def _remove_provider(self) -> None:
        row = self._get_selected_row()
        if row < 0:
            return
        prov = self._config.providers[row]
        reply = QMessageBox.question(
            self,
            "移除服务商",
            f"确定移除 {prov.name} 吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._config.providers.pop(row)
            self._populate_table()
            self.config_changed.emit()

    def _save_and_close(self) -> None:
        # Update enabled states from checkboxes
        for row, prov in enumerate(self._config.providers):
            cb = self._table.cellWidget(row, 0)
            if cb:
                prov.enabled = cb.isChecked()

        self._config.refresh_interval_seconds = self._refresh_spin.value()
        save_config(self._config)
        self.config_changed.emit()
        self.close()
