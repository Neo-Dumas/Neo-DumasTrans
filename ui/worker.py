# ui/worker.py
import sys
import asyncio
from PyQt5.QtCore import QThread, pyqtSignal


class AsyncPdfWorker(QThread):
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, async_func, *args, **kwargs):
        super().__init__()
        self.async_func = async_func
        self.args = args
        self.kwargs = kwargs

    def run(self):
        try:
            if sys.platform == "win32":
                asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(self.async_func(*self.args, **self.kwargs))
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))
        finally:
            loop.close()