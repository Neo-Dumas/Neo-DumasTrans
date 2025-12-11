from PyQt5.QtWidgets import (
    QGroupBox, QVBoxLayout, QHBoxLayout, QComboBox, QLineEdit, QSpinBox,
    QLabel, QCheckBox, QPushButton, QFileDialog, QWidget
)
from PyQt5.QtCore import Qt
import os


class ModelConfigWidget:
    def __init__(self):
        self.run_mode_combo = None

        # 云端相关
        self.llm_combo = None
        self.api_key_edit = None
        self.show_api_checkbox = None
        self.base_url_edit = None
        self.model_name_edit = None

        # 本地相关
        self.local_model_path_edit = None
        self.browse_local_model_button = None

        # 公共
        self.max_concurrent_translate_spinbox = None

        # 容器
        self.cloud_widget = None
        self.local_widget = None

        self.group_box = self._build_ui()
        self._setup_connections()

    def _build_ui(self):
        group = QGroupBox("翻译模型配置（Translation Model Configuration）")
        group.setFlat(True)
        group.setObjectName("modelConfigGroup")  # 可选：为分组框命名
        main_layout = QVBoxLayout(group)
        main_layout.setSpacing(12)

        # === 运行模式选择 ===
        mode_layout = QHBoxLayout()
        mode_label = QLabel("运行模式（Run Mode）:")
        mode_label.setObjectName("runModeLabel")
        self.run_mode_combo = QComboBox()
        self.run_mode_combo.setObjectName("runModeCombo")
        self.run_mode_combo.addItem("云端 API 模式（Cloud API Mode）", "cloud")
        self.run_mode_combo.addItem("本地模型模式（Local Model Mode）", "local")
        mode_layout.addWidget(mode_label)
        mode_layout.addWidget(self.run_mode_combo)
        main_layout.addLayout(mode_layout)

        # === 云端配置区域 ===
        self.cloud_widget = QWidget()
        self.cloud_widget.setObjectName("cloudConfigWidget")
        cloud_layout = QVBoxLayout(self.cloud_widget)
        cloud_layout.setSpacing(10)
        cloud_layout.setContentsMargins(0, 0, 0, 0)

        # 大模型选择
        llm_layout = QHBoxLayout()
        llm_label = QLabel("大模型（LLM）:")
        llm_label.setObjectName("llmLabel")
        self.llm_combo = QComboBox()
        self.llm_combo.setObjectName("llmCombo")
        self._update_llm_options("cloud")
        llm_layout.addWidget(llm_label)
        llm_layout.addWidget(self.llm_combo)
        cloud_layout.addLayout(llm_layout)

        # Base URL
        base_layout = QHBoxLayout()
        base_label = QLabel("Base URL:")
        base_label.setObjectName("baseUrlLabel")
        self.base_url_edit = QLineEdit()
        self.base_url_edit.setObjectName("baseUrlEdit")
        self.base_url_edit.setPlaceholderText("例如：https://api.deepseek.com（e.g., https://api.deepseek.com）")
        base_layout.addWidget(base_label)
        base_layout.addWidget(self.base_url_edit)
        cloud_layout.addLayout(base_layout)

        # 模型代号
        model_name_layout = QHBoxLayout()
        model_name_label = QLabel("模型代号（Model Name）:")
        model_name_label.setObjectName("modelNameLabel")
        self.model_name_edit = QLineEdit()
        self.model_name_edit.setObjectName("modelNameEdit")
        self.model_name_edit.setPlaceholderText("如：deepseek-chat、qwen-max、glm-4、your-model")
        model_name_layout.addWidget(model_name_label)
        model_name_layout.addWidget(self.model_name_edit)
        cloud_layout.addLayout(model_name_layout)

        # API Key
        api_layout = QHBoxLayout()
        api_label = QLabel("API Key:")
        api_label.setObjectName("apiKeyLabel")
        self.api_key_edit = QLineEdit()
        self.api_key_edit.setObjectName("apiKeyEdit")
        self.api_key_edit.setPlaceholderText("请输入 API Key（Enter API Key）")
        self.api_key_edit.setEchoMode(QLineEdit.Password)
        self.show_api_checkbox = QCheckBox("显示（Show）")
        self.show_api_checkbox.setObjectName("showApiKeyCheckbox")
        api_layout.addWidget(api_label)
        api_layout.addWidget(self.api_key_edit)
        api_layout.addWidget(self.show_api_checkbox)
        cloud_layout.addLayout(api_layout)

        main_layout.addWidget(self.cloud_widget)

        # === 本地配置区域 ===
        self.local_widget = QWidget()
        self.local_widget.setObjectName("localConfigWidget")
        local_layout = QVBoxLayout(self.local_widget)
        local_layout.setSpacing(10)
        local_layout.setContentsMargins(0, 0, 0, 0)

        # 本地模型路径（文件）
        local_model_layout = QHBoxLayout()
        local_model_label = QLabel("本地模型路径（Model Path）:")
        local_model_label.setObjectName("localModelPathLabel")
        self.local_model_path_edit = QLineEdit()
        self.local_model_path_edit.setObjectName("localModelPathEdit")
        default_local_model = os.path.join("models", "Hunyuan-MT-7B-GGUF", "Hunyuan-MT-7B.Q4_K_S.gguf")
        self.local_model_path_edit.setText(default_local_model)
        self.local_model_path_edit.setPlaceholderText("请选择 .gguf 模型文件（Select .gguf model file）")

        self.browse_local_model_button = QPushButton("浏览（Browse）")
        self.browse_local_model_button.setObjectName("browseLocalModelButton")

        local_model_layout.addWidget(local_model_label)
        local_model_layout.addWidget(self.local_model_path_edit)
        local_model_layout.addWidget(self.browse_local_model_button)
        local_layout.addLayout(local_model_layout)

        main_layout.addWidget(self.local_widget)

        # === 并发数量（仅云端模式）===
        self.concurrent_widget = QWidget()
        self.concurrent_widget.setObjectName("concurrentWidget")
        concurrent_layout = QHBoxLayout(self.concurrent_widget)
        concurrent_layout.setContentsMargins(0, 0, 0, 0)

        concurrent_label = QLabel("并发数量（Concurrency）:")
        concurrent_label.setObjectName("concurrencyLabel")
        self.max_concurrent_translate_spinbox = QSpinBox()
        self.max_concurrent_translate_spinbox.setObjectName("concurrencySpinbox")
        self.max_concurrent_translate_spinbox.setMinimum(1)
        self.max_concurrent_translate_spinbox.setMaximum(20)
        self.max_concurrent_translate_spinbox.setValue(5)

        concurrent_layout.addWidget(concurrent_label)
        concurrent_layout.addWidget(self.max_concurrent_translate_spinbox)
        concurrent_layout.addStretch()

        main_layout.addWidget(self.concurrent_widget)

        # 初始化显示状态
        self._switch_mode_ui("cloud")

        return group

    def _setup_connections(self):
        self.run_mode_combo.currentTextChanged.connect(self.on_run_mode_changed)
        self.llm_combo.currentTextChanged.connect(self._on_llm_changed)
        self.show_api_checkbox.toggled.connect(
            lambda checked: self.api_key_edit.setEchoMode(QLineEdit.Normal if checked else QLineEdit.Password)
        )
        self.browse_local_model_button.clicked.connect(self._browse_local_model_file)

    def _update_llm_options(self, mode):
        self.llm_combo.clear()
        if mode == "cloud":
            self.llm_combo.addItem("DeepSeek", "deepseek")
            self.llm_combo.addItem("Qwen-Max", "qwen-max")
            self.llm_combo.addItem("智谱 GLM-4（Zhipu GLM-4）", "glm-4")
            self.llm_combo.addItem("自定义模型（Custom Model）", "custom")

    def _switch_mode_ui(self, mode):
        """切换 UI 显示"""
        is_local = (mode == "local")
        self.cloud_widget.setVisible(not is_local)
        self.local_widget.setVisible(is_local)
        # 并发设置仅在云端模式显示
        self.concurrent_widget.setVisible(not is_local)

    def on_run_mode_changed(self):
        mode = self.run_mode_combo.currentData()
        self._switch_mode_ui(mode)

        if mode == "cloud":
            self._on_llm_changed()  # 自动填充默认值
        elif mode == "local":
            current = self.local_model_path_edit.text().strip()
            if not current:
                default_path = os.path.join("models", "Hunyuan-MT-7B-GGUF", "Hunyuan-MT-7B.Q4_K_S.gguf")
                self.local_model_path_edit.setText(default_path)

    def _on_llm_changed(self):
        if self.run_mode_combo.currentData() != "cloud":
            return

        model_id = self.llm_combo.currentData()
        if model_id == "custom":
            return

        defaults = {
            "deepseek": {
                "base_url": "https://api.deepseek.com",
                "model_name": "deepseek-chat"
            },
            "qwen-max": {
                "base_url": "https://dashscope.aliyuncs.com",
                "model_name": "qwen-max"
            },
            "glm-4": {
                "base_url": "https://open.bigmodel.cn/api/paas/v4",
                "model_name": "glm-4"
            }
        }

        if model_id in defaults:
            info = defaults[model_id]
            if not self.base_url_edit.text().strip():
                self.base_url_edit.setText(info["base_url"])
            if not self.model_name_edit.text().strip():
                self.model_name_edit.setText(info["model_name"])

    def _browse_local_model_file(self):
        current_text = self.local_model_path_edit.text().strip()
        start_dir = os.path.dirname(current_text) if os.path.isfile(current_text) else os.getcwd()
        file_path, _ = QFileDialog.getOpenFileName(
            None,
            "选择本地 GGUF 翻译模型文件（Select Local GGUF Translation Model）",
            start_dir,
            "GGUF 模型文件 (*.gguf);;所有文件 (*)"
        )
        if file_path:
            self.local_model_path_edit.setText(file_path)

    def get_widgets(self):
        return {
            'run_mode_combo': self.run_mode_combo,
            'llm_combo': self.llm_combo,
            'api_key_edit': self.api_key_edit,
            'show_api_checkbox': self.show_api_checkbox,
            'base_url_edit': self.base_url_edit,
            'model_name_edit': self.model_name_edit,
            'local_model_path_edit': self.local_model_path_edit,
            'max_concurrent_translate_spinbox': self.max_concurrent_translate_spinbox,
        }