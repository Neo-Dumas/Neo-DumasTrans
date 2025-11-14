# ui/translate_settings.py
from PyQt5.QtWidgets import QGroupBox, QVBoxLayout, QHBoxLayout, QComboBox, QLabel


class TranslateSettingsWidget:
    def __init__(self):
        self.target_lang_combo = None
        self.group_box = self._build_ui()

    def _build_ui(self):
        group = QGroupBox("翻译设置")
        group.setFlat(True)
        layout = QVBoxLayout(group)

        lang_layout = QHBoxLayout()
        self.target_lang_combo = QComboBox()
        # 可在外部初始化语言列表，这里先留空或设默认
        self.target_lang_combo.addItems(["简体中文", "English", "日本語", "한국어"])
        lang_layout.addWidget(QLabel("目标语言:"))
        lang_layout.addWidget(self.target_lang_combo)
        lang_layout.addStretch()
        layout.addLayout(lang_layout)

        return group

    def get_widgets(self):
        return {
            'target_lang_combo': self.target_lang_combo,
        }