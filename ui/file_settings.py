# ui/file_settings.py
from PyQt5.QtWidgets import QGroupBox, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton, QLabel, QComboBox


class FileSettingsWidget:
    def __init__(self):
        self.pdf_path_edit = None
        self.output_dir_edit = None
        self.pdf_type_combo = None
        self.pdf_button = None
        self.output_button = None

        self.group_box = self._build_ui()

    def _build_ui(self):
        group = QGroupBox("文件设置")
        group.setFlat(True)
        layout = QVBoxLayout(group)
        layout.setSpacing(10)

        # PDF 文件选择
        pdf_layout = QHBoxLayout()
        self.pdf_path_edit = QLineEdit()
        self.pdf_path_edit.setPlaceholderText("请选择 PDF 文件")
        self.pdf_path_edit.setReadOnly(True)
        self.pdf_button = QPushButton("选择 PDF")
        self.pdf_button.setFixedWidth(110)
        pdf_layout.addWidget(self.pdf_path_edit)
        pdf_layout.addWidget(self.pdf_button)
        layout.addLayout(pdf_layout)

        # 输出目录
        output_layout = QHBoxLayout()
        self.output_dir_edit = QLineEdit()
        self.output_dir_edit.setPlaceholderText("请选择输出文件夹")
        self.output_dir_edit.setReadOnly(True)
        self.output_button = QPushButton("选择目录")
        self.output_button.setFixedWidth(110)
        output_layout.addWidget(self.output_dir_edit)
        output_layout.addWidget(self.output_button)
        layout.addLayout(output_layout)

        return group

    def get_widgets(self):
        return {
            'pdf_path_edit': self.pdf_path_edit,
            'output_dir_edit': self.output_dir_edit,
            'pdf_type_combo': self.pdf_type_combo,
            'pdf_button': self.pdf_button,
            'output_button': self.output_button,
        }