from PyQt5.QtWidgets import (
    QGroupBox, QVBoxLayout, QHBoxLayout, QLineEdit, QLabel,
    QCheckBox
)
from PyQt5.QtCore import Qt


class OcrSettingsWidget:
    def __init__(self):
        self.mineru_api_key_edit = None
        self.show_mineru_api_checkbox = None
        self.mineru_base_url_edit = None

        self.group_box = self._build_ui()
        self._setup_connections()

    def _build_ui(self):
        group = QGroupBox("OCR 设置（MinerU OCR Settings）")
        group.setFlat(True)
        group.setObjectName("ocrSettingsGroup")  # 可选：为分组框也命名
        main_layout = QVBoxLayout(group)
        main_layout.setSpacing(12)

        # MinerU API Token
        api_layout = QHBoxLayout()
        api_label = QLabel("MinerU Token:")
        api_label.setObjectName("mineruApiLabel")

        self.mineru_api_key_edit = QLineEdit()
        self.mineru_api_key_edit.setObjectName("mineruApiKeyEdit")  # ← 关键
        self.mineru_api_key_edit.setPlaceholderText("请输入 MinerU OCR 的 API Token")
        self.mineru_api_key_edit.setEchoMode(QLineEdit.Password)

        self.show_mineru_api_checkbox = QCheckBox("显示（Show）")
        self.show_mineru_api_checkbox.setObjectName("showMineruApiCheckbox")  # ← 关键

        api_layout.addWidget(api_label)
        api_layout.addWidget(self.mineru_api_key_edit)
        api_layout.addWidget(self.show_mineru_api_checkbox)
        main_layout.addLayout(api_layout)

        # MinerU Base URL
        url_layout = QHBoxLayout()
        url_label = QLabel("MinerU URL:")
        url_label.setObjectName("mineruUrlLabel")

        self.mineru_base_url_edit = QLineEdit()
        self.mineru_base_url_edit.setObjectName("mineruBaseUrlEdit")  # ← 关键
        self.mineru_base_url_edit.setPlaceholderText("例如：https://api.mineru.com/v1（e.g., https://api.mineru.com/v1）")

        url_layout.addWidget(url_label)
        url_layout.addWidget(self.mineru_base_url_edit)
        main_layout.addLayout(url_layout)

        return group

    def _setup_connections(self):
        self.show_mineru_api_checkbox.toggled.connect(
            lambda checked: self.mineru_api_key_edit.setEchoMode(QLineEdit.Normal if checked else QLineEdit.Password)
        )

    def get_widgets(self):
        return {
            'mineru_api_key_edit': self.mineru_api_key_edit,
            'show_mineru_api_checkbox': self.show_mineru_api_checkbox,
            'mineru_base_url_edit': self.mineru_base_url_edit,
        }