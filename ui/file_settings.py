from PyQt5.QtWidgets import QGroupBox, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit


class FileSettingsWidget:
    def __init__(self):
        # 必须初始化所有控件引用和 group_box
        self.pdf_path_edit = None
        self.output_dir_edit = None
        self.pdf_button = None
        self.output_button = None

        self.group_box = self._build_ui()  # ← 关键：必须有这行！

    def _build_ui(self):
        group = QGroupBox("文件设置（File Settings）")
        group.setFlat(True)
        group.setObjectName("fileSettingsGroup")  # 可选：为分组框也命名
        layout = QVBoxLayout(group)
        layout.setSpacing(10)

        # PDF 文件选择
        pdf_layout = QHBoxLayout()
        self.pdf_path_edit = QLineEdit()
        self.pdf_path_edit.setObjectName("pdfPathEdit")  # ← 添加 objectName
        self.pdf_path_edit.setPlaceholderText("请选择 PDF 文件（Select PDF File）")
        self.pdf_path_edit.setReadOnly(True)

        self.pdf_button = QPushButton("选择 PDF（Select PDF）")
        self.pdf_button.setObjectName("selectPdfButton")  # ← 添加 objectName
        pdf_layout.addWidget(self.pdf_path_edit)
        pdf_layout.addWidget(self.pdf_button)
        layout.addLayout(pdf_layout)

        # 输出目录
        output_layout = QHBoxLayout()
        self.output_dir_edit = QLineEdit()
        self.output_dir_edit.setObjectName("outputDirEdit")  # ← 添加 objectName
        self.output_dir_edit.setPlaceholderText("请选择输出文件夹（Select Output Folder）")
        self.output_dir_edit.setReadOnly(True)

        self.output_button = QPushButton("选择目录（Select Folder）")
        self.output_button.setObjectName("selectOutputButton")  # ← 添加 objectName
        output_layout.addWidget(self.output_dir_edit)
        output_layout.addWidget(self.output_button)
        layout.addLayout(output_layout)

        return group

    def get_widgets(self):
        return {
            'pdf_path_edit': self.pdf_path_edit,
            'output_dir_edit': self.output_dir_edit,
            'pdf_button': self.pdf_button,
            'output_button': self.output_button,
        }