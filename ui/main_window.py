# ui/main_window.py

from .ui_components import PdfTranslationUI
from .controllers import TranslationController
from PyQt5.QtWidgets import QMainWindow, QDesktopWidget


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Neo-Dumas Trans")
        self.resize(1280, 720)

        # 创建 UI 组件
        self.ui = PdfTranslationUI(self)

        # 直接将 UI 的完整 widget 设为中央部件
        self.setCentralWidget(self.ui.get_widget())

        # 创建控制器
        self.controller = TranslationController(self.ui)

        # 窗口居中
        self.center_window()

    def center_window(self):
        """在可用屏幕区域居中，并略往上提"""
        screen = QDesktopWidget().availableGeometry()
        size = self.frameGeometry()

        x = (screen.width() - size.width()) // 2 + screen.x()
        y = (screen.height() - size.height()) // 2 + screen.y() - 150
        y = max(y, 0)

        self.move(x, y)