# ui/ui_components.py
from PyQt5.QtWidgets import (
    QVBoxLayout, QLabel, QHBoxLayout, QPushButton, QWidget,
    QComboBox, QSizePolicy
)
from PyQt5.QtGui import QPixmap, QIcon
from PyQt5.QtCore import Qt, QSize, QUrl
from PyQt5.QtSvg import QSvgRenderer
from PyQt5.QtGui import QImage, QPainter, QDesktopServices
import os

from .file_settings import FileSettingsWidget
from .ocr_settings import OcrSettingsWidget
from .model_config import ModelConfigWidget
from .translate_settings import TranslateSettingsWidget


class PdfTranslationUI:
    def __init__(self, parent):
        self.parent = parent
        self.widgets = {}
        self._build_ui()

    def _build_ui(self):
        # === 外层水平布局：左右留白（用于居中）===
        outer_layout = QHBoxLayout()
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)
        outer_layout.addStretch()  # 左侧空白

        # === 中央容器：固定总宽 = left + gap + right ===
        COLUMN_WIDTH = 540      # 每栏宽度（可根据内容调整）
        GAP = 36                # 两栏间距

        central_widget = QWidget()
        central_layout = QHBoxLayout()
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(GAP)

        # --- 左侧栏（固定宽度）---
        left_widget = QWidget()
        left_widget.setFixedWidth(COLUMN_WIDTH)
        left_layout = QVBoxLayout()
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(16)

        # 文件设置
        self.file_widget = FileSettingsWidget()
        file_group = self.file_widget.group_box
        file_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        left_layout.addWidget(file_group)
        self.widgets.update(self.file_widget.get_widgets())

        # PDF 类型选择
        type_layout = QHBoxLayout()
        type_layout.setContentsMargins(0, 0, 0, 0)
        self.pdf_type_combo = QComboBox()
        self.pdf_type_combo.setObjectName("pdfTypeCombo")  # ← 添加 objectName
        self.pdf_type_combo.addItem("文字型 PDF（Text-based PDF）", "txt")
        self.pdf_type_combo.addItem("图片型 PDF（Image-based PDF + OCR）", "ocr")
        self.pdf_type_combo.addItem("图片型 PDF（VLM 模式）(Image-based PDF + VLM)", "vlm")
        type_layout.addWidget(QLabel("PDF 类型（PDF Type）:"))
        type_layout.addWidget(self.pdf_type_combo)
        type_layout.addStretch()
        left_layout.addLayout(type_layout)
        self.widgets['pdf_type_combo'] = self.pdf_type_combo

        # OCR 设置（初始隐藏，固定高度）
        self.ocr_widget = OcrSettingsWidget()
        self.ocr_widget.group_box.setVisible(False)
        self.ocr_widget.group_box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        left_layout.addWidget(self.ocr_widget.group_box)
        self.widgets.update(self.ocr_widget.get_widgets())

        left_layout.addStretch()  # 底部弹性，防止控件被拉高
        left_widget.setLayout(left_layout)

        # --- 右侧栏（固定宽度）---
        right_widget = QWidget()
        right_widget.setFixedWidth(COLUMN_WIDTH)
        right_layout = QVBoxLayout()
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(16)

        # 翻译设置（在上）
        self.translate_widget = TranslateSettingsWidget()
        right_layout.addWidget(self.translate_widget.group_box)
        self.widgets.update(self.translate_widget.get_widgets())

        # 模型配置（在下）
        self.model_widget = ModelConfigWidget()
        right_layout.addWidget(self.model_widget.group_box)
        self.widgets.update(self.model_widget.get_widgets())

        right_layout.addStretch()  # 底部弹性
        right_widget.setLayout(right_layout)

        # 添加左右栏到中央容器
        central_layout.addWidget(left_widget)
        central_layout.addWidget(right_widget)
        central_widget.setLayout(central_layout)

        # 将中央容器加入外层（实现居中）
        outer_layout.addWidget(central_widget)
        outer_layout.addStretch()  # 右侧空白

        # === Logo + 标题（放在最顶部，居中）===
        top_layout = QVBoxLayout()
        top_layout.setSpacing(24)
        top_layout.setContentsMargins(32, 32, 32, 24)

        # Logo
        logo_label = QLabel()
        logo_label.setAlignment(Qt.AlignCenter)
        logo_label.setObjectName("logoLabel")  # ← 添加 objectName
        top_layout.addWidget(logo_label)

        # 修改：logo.svg 现在位于 icon/logo.svg
        logo_svg_path = os.path.join(os.path.dirname(__file__), "..", "icon", "logo.svg")
        logo_png_path = os.path.join(os.path.dirname(__file__), "..", "icon", "logo.png")  # 兼容png备用
        max_size = 240

        pixmap = None
        if os.path.exists(logo_svg_path):
            renderer = QSvgRenderer(logo_svg_path)
            if renderer.isValid():
                default_size = renderer.defaultSize()
                if default_size.isEmpty():
                    default_size = QSize(100, 100)
                scaled_size = default_size.scaled(max_size, max_size, Qt.KeepAspectRatio)
                image = QImage(scaled_size, QImage.Format_ARGB32)
                image.fill(Qt.transparent)
                painter = QPainter(image)
                renderer.render(painter)
                painter.end()
                pixmap = QPixmap.fromImage(image)
        elif os.path.exists(logo_png_path):
            original_pixmap = QPixmap(logo_png_path)
            if not original_pixmap.isNull():
                scaled_size = original_pixmap.size().scaled(max_size, max_size, Qt.KeepAspectRatio)
                pixmap = original_pixmap.scaled(scaled_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)

        if pixmap and not pixmap.isNull():
            logo_label.setPixmap(pixmap)
        else:
            print("警告：未找到有效的 icon/logo.svg 或 icon/logo.png，图标将不显示。")

        # 标题
        title = QLabel(
            "能够有效处理公式、表格、图片、复杂排版和超大文件的PDF翻译软件\n"
            "PDF Translator for Formulas, Tables, Images, Complex Layouts & Large Files"
        )
        title.setAlignment(Qt.AlignCenter)
        title.setWordWrap(True)
        title.setObjectName("mainTitle")  # ← 添加 objectName
        top_layout.addWidget(title)

        # 创建顶部 widget 并加入 outer_layout 的最前面
        top_widget = QWidget()
        top_widget.setLayout(top_layout)

        # 最终主布局：顶部 + 中央两栏
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        main_layout.addWidget(top_widget)
        main_layout.addLayout(outer_layout)

        # === 独立的“开始翻译”按钮（居中于底部）===
        bottom_button_layout = QHBoxLayout()
        bottom_button_layout.setContentsMargins(0, 8, 0, 24)  # 减少下边距，因为下面还有图标
        bottom_button_layout.addStretch()

        self.start_button = QPushButton("🚀 开始翻译（Start Translation）")
        self.start_button.setObjectName("startButton")
        self.start_button.setProperty("translating", False)
        self.start_button.setMaximumWidth(400)
        bottom_button_layout.addWidget(self.start_button)

        bottom_button_layout.addStretch()
        self.widgets['start_button'] = self.start_button

        main_layout.addLayout(bottom_button_layout)

        # === 社交媒体图标（由 QSS 控制样式与尺寸）===
        social_widget = QWidget()
        social_widget.setObjectName("socialWidget")  # ← 关键：用于 QSS 选择
        social_layout = QHBoxLayout(social_widget)
        social_layout.setContentsMargins(0, 0, 0, 32)
        social_layout.setSpacing(0)  # 间距由 QSS margin 控制更精准

        icon_size = QSize(28, 28)  # 可保留一个基础大小，但实际显示由 QSS 覆盖

        # Bilibili
        bilibili_btn = QPushButton()
        bilibili_btn.setObjectName("socialButton")
        bilibili_btn.setProperty("platform", "bilibili")
        bilibili_btn.setIcon(self._load_icon("icon/bilibili.svg"))
        bilibili_btn.setIconSize(icon_size)
        bilibili_btn.clicked.connect(lambda: self._open_url("https://space.bilibili.com/1432840603?spm_id_from=333.1007.0.0"))
        bilibili_btn.setCursor(Qt.PointingHandCursor)
        social_layout.addWidget(bilibili_btn)

        # Zhihu
        zhihu_btn = QPushButton()
        zhihu_btn.setObjectName("socialButton")
        zhihu_btn.setProperty("platform", "zhihu")
        zhihu_btn.setIcon(self._load_icon("icon/Zhihu_logo.svg"))
        zhihu_btn.setIconSize(icon_size)
        zhihu_btn.clicked.connect(lambda: self._open_url("https://www.zhihu.com/people/47-53-12-57"))
        zhihu_btn.setCursor(Qt.PointingHandCursor)
        social_layout.addWidget(zhihu_btn)

        # GitHub
        github_btn = QPushButton()
        github_btn.setObjectName("socialButton")
        github_btn.setProperty("platform", "github")
        github_btn.setIcon(self._load_icon("icon/github-mark-white.png"))
        github_btn.setIconSize(icon_size)
        github_btn.clicked.connect(lambda: self._open_url("https://github.com/Neo-Dumas"))
        github_btn.setCursor(Qt.PointingHandCursor)
        social_layout.addWidget(github_btn)

        main_layout.addWidget(social_widget, alignment=Qt.AlignCenter)

        # === 信号与样式 ===
        self.pdf_type_combo.currentTextChanged.connect(self._on_pdf_type_changed)
        self._on_pdf_type_changed()
        self._apply_styles()

        # 保存主 widget
        self._main_widget = QWidget()
        self._main_widget.setLayout(main_layout)

    def _load_icon(self, relative_path):
        full_path = os.path.join(os.path.dirname(__file__), "..", relative_path)
        if os.path.exists(full_path):
            return QIcon(full_path)
        else:
            print(f"警告：图标文件未找到: {full_path}")
            return QIcon()

    def _open_url(self, url):
        QDesktopServices.openUrl(QUrl(url))

    def _on_pdf_type_changed(self):
        current_type = self.pdf_type_combo.currentData()
        show_ocr = (current_type == "vlm")  # 请根据实际逻辑确认
        self.ocr_widget.group_box.setVisible(show_ocr)

    def _apply_styles(self):
        style_file = os.path.join(os.path.dirname(__file__), "styles.qss")
        try:
            with open(style_file, "r", encoding="utf-8") as f:
                self.parent.setStyleSheet(f.read())
        except Exception as e:
            print(f"样式加载失败: {e}")

    def get_widget(self):
        return self._main_widget

    def get_layout(self):
        return self._main_widget.layout()

    def set_pdf_filename(self, filename):
        self.file_widget.pdf_path_edit.setText(os.path.basename(filename) if filename else "")

    def set_output_dir(self, dir_path):
        self.file_widget.output_dir_edit.setText(dir_path or "")

    def set_start_button_translating(self, translating=True):
        self.start_button.setProperty("translating", translating)
        if translating:
            self.start_button.setText("🔄 翻译中...（Translating...）")
            self.start_button.setEnabled(False)
        else:
            self.start_button.setText("🚀 开始翻译（Start Translation）")
            self.start_button.setEnabled(True)
        self.start_button.style().unpolish(self.start_button)
        self.start_button.style().polish(self.start_button)