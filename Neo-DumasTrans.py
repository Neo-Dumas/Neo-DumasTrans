# main.py
# 第1~4行（不要有任何 import 在它前面！）
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# 从这里开始你的正常代码
import logging
import atexit
from pathlib import Path
from ui.main_window import MainWindow
from PyQt5.QtWidgets import QApplication

# 导入清理工具
from cleanup import clear_workdir_if_too_large


# 设置debug文件
debug_file = os.path.join(os.getcwd(), 'debug.txt')

# 配置日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(debug_file, mode='w', encoding='utf-8')
    ]
)

logger = logging.getLogger(__name__)
logger.info(f"🔧 Debug信息将保存到: {debug_file}")

# 注册退出时的处理函数
def on_exit():
    logger.info("应用程序退出")
    print(f"✅ Debug文件已生成: {debug_file}")

atexit.register(on_exit)


# ========== 主程序入口 ==========
if __name__ == "__main__":
    clear_workdir_if_too_large()
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    logger.info("应用程序启动完成")
    sys.exit(app.exec_())