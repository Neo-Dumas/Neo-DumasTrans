# ui/controllers.py

import os
from PyQt5.QtWidgets import QMessageBox, QFileDialog
from core.image_pdf_translator import translate_image_pdf
from .worker import AsyncPdfWorker
from .config_manager import load_global_settings, save_global_settings, load_api_config, save_api_config
from .llm_config import LLM_DISPLAY_TO_KEY, LLM_DEFAULTS, LLM_KEY_TO_DISPLAY
from .language import LANG_DISPLAY_TO_CODE, LANG_CODE_TO_DISPLAY


class TranslationController:
    def __init__(self, ui_components):
        self.ui = ui_components
        self.pdf_path = ""
        self.output_dir = ""
        self.current_llm_key = "deepseek"
        self.target_lang_code = "zh"
        self.pdf_type = "txt"  # 默认为文本型
        self.mineru_api_key = ""
        self.mineru_base_url = ""
        self.local_model_path = ""  # 新增：本地模型路径

        # 初始化 UI 数据
        self._setup_initial_data()
        # 绑定事件
        self._connect_signals()

    def _setup_initial_data(self):
        """加载初始设置并填充 UI"""
        settings = load_global_settings()
        self.pdf_path = settings.get("pdf_path", "")
        self.output_dir = settings.get("output_dir", "")
        self.target_lang_code = settings.get("target_lang_code", "zh")
        llm_provider = settings.get("llm_provider", "deepseek")
        max_concurrent_translate = settings.get("max_concurrent_translate", 5)  # 与 UI 默认值一致
        # ✅ 加载并恢复 PDF 类型
        self.pdf_type = settings.get("pdf_type", "txt")

        pdf_type_combo = self.ui.widgets['pdf_type_combo']
        index = pdf_type_combo.findData(self.pdf_type)
        if index >= 0:
            pdf_type_combo.setCurrentIndex(index)

        # ✅ 加载 MinerU 配置
        mineru_config = load_api_config("mineru")
        self.mineru_api_key = mineru_config.get("api_key", "")
        self.mineru_base_url = mineru_config.get("base_url", "https://mineru.net/api/v4")

        # 填充下拉框（LLM 和目标语言）
        llm_combo = self.ui.widgets['llm_combo']
        target_lang_combo = self.ui.widgets['target_lang_combo']

        # 使用 LLM_DISPLAY_TO_KEY 的键作为显示项（与 model_config.py 一致）
        llm_combo.clear()
        llm_combo.addItems(list(LLM_DISPLAY_TO_KEY.keys()))
        target_lang_combo.clear()
        target_lang_combo.addItems(list(LANG_DISPLAY_TO_CODE.keys()))

        # 恢复选择项
        default_lang = LANG_CODE_TO_DISPLAY.get(self.target_lang_code, "中文")
        if default_lang in LANG_DISPLAY_TO_CODE:
            target_lang_combo.setCurrentText(default_lang)

        default_llm = LLM_KEY_TO_DISPLAY.get(llm_provider, "DeepSeek")
        if default_llm in LLM_DISPLAY_TO_KEY:
            llm_combo.setCurrentText(default_llm)

        # 显示路径
        self.ui.set_pdf_filename(self.pdf_path)
        self.ui.set_output_dir(self.output_dir)

        # ✅ 设置 MinerU 字段
        self.ui.widgets['mineru_api_key_edit'].setText(self.mineru_api_key)
        self.ui.widgets['mineru_base_url_edit'].setText(self.mineru_base_url)

        # ✅ 恢复并发数（与 UI 默认值 5 一致）
        self.ui.widgets['max_concurrent_translate_spinbox'].setValue(max_concurrent_translate)

        # ✅ 恢复运行模式
        run_mode_combo = self.ui.widgets['run_mode_combo']
        saved_run_mode = settings.get("run_mode", "cloud")
        index = run_mode_combo.findData(saved_run_mode)
        if index >= 0:
            run_mode_combo.setCurrentIndex(index)
        else:
            run_mode_combo.setCurrentIndex(0)

        # ✅ 恢复本地模型路径
        self.local_model_path = settings.get("local_model_path", "")
        if not self.local_model_path:
            # 如果未保存，使用 UI 中的默认路径（与 model_config.py 一致）
            self.local_model_path = os.path.join("models", "Hunyuan-MT-7B-GGUF", "Hunyuan-MT-7B.Q4_K_S.gguf")
        self.ui.widgets['local_model_path_edit'].setText(self.local_model_path)

        # 触发一次 LLM 配置更新（仅当是云端模式时有效）
        self.on_llm_changed(llm_combo.currentText())

    def toggle_mineru_api_visibility(self, checked):
        edit = self.ui.widgets['mineru_api_key_edit']
        mode = edit.Normal if checked else edit.Password
        edit.setEchoMode(mode)

    def toggle_api_visibility(self, checked):
        edit = self.ui.widgets['api_key_edit']
        mode = edit.Normal if checked else edit.Password
        edit.setEchoMode(mode)

    def _connect_signals(self):
        """绑定所有 UI 信号"""
        w = self.ui.widgets
        w['pdf_button'].clicked.connect(self.select_pdf_file)
        w['output_button'].clicked.connect(self.select_output_dir)
        w['llm_combo'].currentTextChanged.connect(self.on_llm_changed)
        w['show_api_checkbox'].toggled.connect(self.toggle_api_visibility)
        w['show_mineru_api_checkbox'].toggled.connect(self.toggle_mineru_api_visibility)
        w['start_button'].clicked.connect(self.start_translation)
        w['pdf_type_combo'].currentTextChanged.connect(self.on_pdf_type_changed)

    def on_llm_changed(self, display_name):
        llm_key = LLM_DISPLAY_TO_KEY.get(display_name, "custom")
        saved = load_api_config(llm_key)
        defaults = LLM_DEFAULTS.get(llm_key, {"base_url": "", "model_name": ""})

        self.ui.widgets['base_url_edit'].setText(saved.get("base_url", defaults["base_url"]))
        self.ui.widgets['model_name_edit'].setText(saved.get("model_name", defaults["model_name"]))
        self.ui.widgets['api_key_edit'].setText(saved.get("api_key", ""))
        self.current_llm_key = llm_key

    def select_pdf_file(self):
        initial_dir = os.path.dirname(self.pdf_path) if self.pdf_path else ""
        file_path, _ = QFileDialog.getOpenFileName(
            self.ui.parent, "选择 PDF 文件", initial_dir, "PDF 文件 (*.pdf)"
        )
        if file_path:
            self.pdf_path = os.path.abspath(file_path)
            self.ui.set_pdf_filename(self.pdf_path)

    def select_output_dir(self):
        initial_dir = self.output_dir if self.output_dir else ""
        dir_path = QFileDialog.getExistingDirectory(self.ui.parent, "选择输出文件夹", initial_dir)
        if dir_path:
            self.output_dir = os.path.abspath(dir_path)
            self.ui.set_output_dir(self.output_dir)

    def start_translation(self):
        # 更新 UI：进入翻译中状态
        if not self.pdf_path or not self.output_dir:
            QMessageBox.warning(self.ui.parent, "输入不完整", "请先选择 PDF 文件和输出目录！")
            return

        start_button = self.ui.widgets['start_button']
        start_button.setText("🔄 翻译中...")
        start_button.setEnabled(False)

        max_concurrent_translate = self.ui.widgets['max_concurrent_translate_spinbox'].value()
        display_lang = self.ui.widgets['target_lang_combo'].currentText()
        target_lang = LANG_DISPLAY_TO_CODE.get(display_lang, "zh")

        # === 获取运行模式 ===
        run_mode_combo = self.ui.widgets['run_mode_combo']
        run_mode = run_mode_combo.currentData()

        api_key = base_url = model_name = None

        if run_mode == "cloud":
            api_key = self.ui.widgets['api_key_edit'].text().strip()
            base_url = self.ui.widgets['base_url_edit'].text().strip()
            model_name = self.ui.widgets['model_name_edit'].text().strip()

            if not api_key or not base_url or not model_name:
                QMessageBox.warning(self.ui.parent, "配置不完整", "请填写 API Key、Base URL 和模型代号！")
                start_button.setEnabled(True)
                start_button.setText("🚀 开始翻译")
                return

            # 保存当前 LLM 的 API 配置
            save_api_config(self.current_llm_key, {
                "api_key": api_key,
                "base_url": base_url,
                "model_name": model_name
            })
        else:
            # === 本地模式 ===
            model_path = self.ui.widgets['local_model_path_edit'].text().strip()
            if not model_path:
                QMessageBox.warning(self.ui.parent, "模型路径为空", "请选择有效的本地 GGUF 模型文件！")
                start_button.setEnabled(True)
                start_button.setText("🚀 开始翻译")
                return
            if not os.path.isfile(model_path):
                QMessageBox.warning(self.ui.parent, "模型文件不存在", f"找不到模型文件：\n{model_path}")
                start_button.setEnabled(True)
                start_button.setText("🚀 开始翻译")
                return

            # 本地模式使用固定标识，实际模型路径通过 model_name 传入
            api_key = "local"
            base_url = "local"
            model_name = model_path  # 👈 关键：传完整路径给后端

        # ✅ MinerU 字段（允许为空）
        mineru_api_key = self.ui.widgets['mineru_api_key_edit'].text().strip()
        mineru_base_url = self.ui.widgets['mineru_base_url_edit'].text().strip()
        # ✅ 保存 MinerU 配置（即使为空也保存，避免下次启动为空白）
        save_api_config("mineru", {
            "api_key": mineru_api_key,
            "base_url": mineru_base_url
        })


        # 保存全局设置（包括本地模型路径和运行模式）
        save_global_settings({
            "pdf_path": self.pdf_path,
            "output_dir": self.output_dir,
            "target_lang_code": target_lang,
            "llm_provider": self.current_llm_key,
            "max_concurrent_translate": max_concurrent_translate,
            "pdf_type": self.pdf_type,
            "run_mode": run_mode,
            "local_model_path": self.ui.widgets['local_model_path_edit'].text().strip(),  # ✅ 保存路径
        })

        # 启动工作线程
        self.worker = AsyncPdfWorker(
            translate_image_pdf,
            pdf_path=self.pdf_path,
            output_dir=self.output_dir,
            target_lang=target_lang,
            api_key=api_key,
            base_url=base_url,
            model_name=model_name,          # 已正确设置为路径或代号
            final_output_dir=self.output_dir,
            max_concurrent_translate=max_concurrent_translate,
            mineru_api_key=mineru_api_key,
            mineru_base_url=mineru_base_url,
            pdf_type=self.pdf_type,
        )
        self.worker.finished.connect(lambda r: self.on_translate_finished(r))
        self.worker.error.connect(lambda e: self.on_translate_error(e))
        self.worker.start()

    def on_translate_finished(self, result):
        start_button = self.ui.widgets['start_button']
        start_button.setEnabled(True)
        start_button.setText("🚀 开始翻译")
        if result.get("success"):
            QMessageBox.information(self.ui.parent, "完成", f"翻译成功！\n输出文件：\n{result['output_path']}")
        else:
            QMessageBox.critical(self.ui.parent, "错误", f"翻译失败：\n{result.get('error', '未知错误')}")

    def on_translate_error(self, error_msg):
        start_button = self.ui.widgets['start_button']
        start_button.setEnabled(True)
        start_button.setText("🚀 开始翻译")
        QMessageBox.critical(self.ui.parent, "异常", f"处理过程中发生异常：\n{error_msg}")

    def on_pdf_type_changed(self):
        combo = self.ui.widgets['pdf_type_combo']
        index = combo.currentIndex()
        if index >= 0:
            self.pdf_type = combo.currentData()
        else:
            self.pdf_type = "txt"
        print(f"PDF 类型已切换为: {self.pdf_type}")