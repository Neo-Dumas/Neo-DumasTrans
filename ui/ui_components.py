# ui/ui_components.py
from PyQt5.QtWidgets import QVBoxLayout, QLabel, QHBoxLayout, QPushButton, QWidget
from PyQt5.QtCore import Qt
import os

from .file_settings import FileSettingsWidget
from .ocr_settings import OcrSettingsWidget
from .model_config import ModelConfigWidget
from .translate_settings import TranslateSettingsWidget
from PyQt5.QtWidgets import QGroupBox, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton, QLabel, QComboBox


class PdfTranslationUI:
    def __init__(self, parent):
        self.parent = parent
        self.layout = QVBoxLayout()
        self.widgets = {}

        self._build_ui()

    def _build_ui(self):
        self.layout.setSpacing(12)
        self.layout.setContentsMargins(16, 16, 16, 16)

        # === 标题 ===
        title = QLabel("能够有效处理公式、表格、图片、复杂排版和超大文件的PDF翻译软件")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("""
            QLabel {
                color: #1e293b;
                font-size: 20px;
                font-weight: bold;
                padding: 8px;
                margin-bottom: 8px;
            }
        """)
        self.layout.addWidget(title)

        # === 文件设置 ===
        self.file_widget = FileSettingsWidget()
        self.layout.addWidget(self.file_widget.group_box)
        self.widgets.update(self.file_widget.get_widgets())

        # === PDF 类型选择（提前创建，用于控制后续模块显示）===
        type_layout = QHBoxLayout()
        self.pdf_type_combo = QComboBox()
        self.pdf_type_combo.addItem("文字型 PDF（本地提取文本）", "txt")
        self.pdf_type_combo.addItem("图片型 PDF（本地 OCR 识别）", "ocr")
        self.pdf_type_combo.addItem("图片型 PDF（VLM 模式，需输入 MinerU Token 或本地部署）", "vlm")
        type_layout.addWidget(QLabel("PDF 类型:"))
        type_layout.addWidget(self.pdf_type_combo)
        self.layout.addLayout(type_layout)
        self.widgets['pdf_type_combo'] = self.pdf_type_combo

        # === OCR 设置（MinerU）—— 初始隐藏 ===
        self.ocr_widget = OcrSettingsWidget()
        self.ocr_widget.group_box.setVisible(False)  # 默认隐藏
        self.layout.addWidget(self.ocr_widget.group_box)
        self.widgets.update(self.ocr_widget.get_widgets())

        # === 翻译模型配置 ===
        self.model_widget = ModelConfigWidget()
        self.layout.addWidget(self.model_widget.group_box)
        self.widgets.update(self.model_widget.get_widgets())

        # === 翻译设置 ===
        self.translate_widget = TranslateSettingsWidget()
        self.layout.addWidget(self.translate_widget.group_box)
        self.widgets.update(self.translate_widget.get_widgets())

        # === 开始按钮 ===
        button_layout = QHBoxLayout()
        self.start_button = QPushButton("🚀 开始翻译")
        self.start_button.setMinimumHeight(40)
        self.start_button.setStyleSheet("""
            QPushButton {
                font-size: 14px;
                font-weight: bold;
                background-color: #4f46e5;
                color: white;
                border: none;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #4338ca;
            }
        """)
        button_layout.addStretch()
        button_layout.addWidget(self.start_button, 0, Qt.AlignCenter)
        button_layout.addStretch()
        self.layout.addLayout(button_layout)
        self.widgets['start_button'] = self.start_button

        # === 连接信号 ===
        self.pdf_type_combo.currentTextChanged.connect(self._on_pdf_type_changed)

        # 初始化 UI 状态
        self._on_pdf_type_changed()

        self._apply_styles()

    def _on_pdf_type_changed(self):
        current_type = self.pdf_type_combo.currentData()
        # 只有在 VLM 模式下才显示 MinerU OCR 设置
        show_ocr = (current_type == "vlm")
        self.ocr_widget.group_box.setVisible(show_ocr)



    def _apply_styles(self):
        style_file = os.path.join(os.path.dirname(__file__), "styles.qss")
        try:
            with open(style_file, "r", encoding="utf-8") as f:
                self.parent.setStyleSheet(f.read())
        except FileNotFoundError:
            print(f"警告: 样式文件未找到: {style_file}，使用默认样式。")
        except Exception as e:
            print(f"加载样式文件失败: {e}")

    def get_layout(self):
        return self.layout

    def set_pdf_filename(self, filename):
        self.file_widget.pdf_path_edit.setText(os.path.basename(filename) if filename else "")

    def set_output_dir(self, dir_path):
        self.file_widget.output_dir_edit.setText(dir_path or "")

    def set_start_button_translating(self, translating=True):
        if translating:
            self.start_button.setText("🔄 翻译中...")
            self.start_button.setEnabled(False)
            self.start_button.setStyleSheet("""
                QPushButton {
                    font-size: 14px;
                    font-weight: bold;
                    background-color: #94a3b8;
                    color: white;
                    border: none;
                    border-radius: 6px;
                }
            """)
        else:
            self.start_button.setText("🚀 开始翻译")
            self.start_button.setEnabled(True)
            self.start_button.setStyleSheet("""
                QPushButton {
                    font-size: 14px;
                    font-weight: bold;
                    background-color: #4f46e5;
                    color: white;
                    border: none;
                    border-radius: 6px;
                }
                QPushButton:hover {
                    background-color: #4338ca;
                }
            """)