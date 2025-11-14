from PyQt5.QtWidgets import QGroupBox, QVBoxLayout, QHBoxLayout, QComboBox, QLabel


class TranslateSettingsWidget:
    def __init__(self):
        self.target_lang_combo = None
        self.group_box = self._build_ui()

    def _build_ui(self):
        group = QGroupBox("翻译设置（Translation Settings）")
        group.setFlat(True)
        layout = QVBoxLayout(group)

        lang_layout = QHBoxLayout()
        self.target_lang_combo = QComboBox()
        # 保留原始语言选项（本身已含中英日韩）
        self.target_lang_combo.addItems(["简体中文", "English", "日本語", "한국어"])
        lang_layout.addWidget(QLabel("目标语言（Target Language）:"))
        lang_layout.addWidget(self.target_lang_combo)
        lang_layout.addStretch()
        layout.addLayout(lang_layout)

        return group

    def get_widgets(self):
        return {
            'target_lang_combo': self.target_lang_combo,
        }