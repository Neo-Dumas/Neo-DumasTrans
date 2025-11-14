# ui/main_window.py

from .ui_components import PdfTranslationUI
from .controllers import TranslationController
from PyQt5.QtWidgets import QMainWindow, QWidget, QDesktopWidget


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Neo-Dumas Trans")
        self.resize(960, 720)

        # 创建 UI 组件
        self.ui = PdfTranslationUI(self)

        # 创建中央控件
        central_widget = QWidget()
        central_widget.setLayout(self.ui.get_layout())
        self.setCentralWidget(central_widget)

        # 创建控制器（自动绑定逻辑）
        self.controller = TranslationController(self.ui)

        # === ✅ 新增：窗口居中显示 ===
        self.center_window()

    def center_window(self):
        """优化版：在可用屏幕区域内居中，并略往上提"""
        from PyQt5.QtWidgets import QDesktopWidget

        screen = QDesktopWidget().availableGeometry()  # 避开任务栏
        size = self.frameGeometry()  # 包含窗口边框的整体大小

        x = (screen.width() - size.width()) // 2 + screen.x()
        y = (screen.height() - size.height()) // 2 + screen.y()

        # 上移 50 像素，避免靠下
        y = y - 50
        y = max(y, 10)  # 确保不贴顶（留 10px 边距）

        self.move(x, y)