import os
import subprocess
import asyncio
import socket
from pathlib import Path
from typing import Optional
from loguru import logger
from ..pipeline_message import PipelineMessage
from ..mineru_engine import run_single_pdf

# 硬编码 MinerU API 可执行文件的相对路径（相对于项目根目录）
MINERU_API_EXE = "python-3.10.11/Scripts/mineru-api.exe"


async def _wait_for_port(host: str, port: int, timeout: float = 30.0) -> bool:
    """异步等待指定 TCP 端口可连接"""
    start = asyncio.get_event_loop().time()
    while asyncio.get_event_loop().time() - start < timeout:
        try:
            # 尝试建立 TCP 连接
            await asyncio.open_connection(host, port)
            return True
        except (OSError, asyncio.TimeoutError):
            await asyncio.sleep(1)
    return False


async def stage_mineru_processor(
    input_queue: asyncio.Queue,
    output_queue: asyncio.Queue,
    mineru_output_dir: Path,
    pdf_type: str,
    concurrency: int,
    mineru_api_key: Optional[str] = None,
    mineru_base_url: Optional[str] = None,
):
    api_process = None

    if pdf_type in ("txt", "ocr"):
        exe_path = Path(MINERU_API_EXE)
        if not exe_path.exists():
            logger.error(f"❌ MinerU API 可执行文件不存在: {exe_path.absolute()}")
            await output_queue.put(None)
            return

        logger.info("🚀 启动 MinerU API 服务 (强制使用 CPU)...")

        env = os.environ.copy()
        env["MINERU_DEVICE_MODE"] = "cpu"

        api_process = subprocess.Popen([
            str(exe_path), "--host", "127.0.0.1", "--port", "8000"
        ], env=env)

        # === 替换原来的 await asyncio.sleep(5) ===
        logger.info("⏳ 等待 MinerU API 端口 8000 就绪...")
        if not await _wait_for_port("127.0.0.1", 8000, timeout=30):
            logger.error("❌ MinerU API 端口 8000 在 30 秒内未就绪")
            if api_process:
                api_process.terminate()
                try:
                    api_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    api_process.kill()
            await output_queue.put(None)
            return
        logger.info("✅ MinerU API 端口 8000 已就绪")
        # === 端口等待结束 ===

    try:
        semaphore = asyncio.Semaphore(concurrency)
        running_tasks = []
        end_signal_received = False

        async def process(msg: PipelineMessage):
            async with semaphore:
                try:
                    loop = asyncio.get_running_loop()
                    result = await loop.run_in_executor(
                        None,
                        run_single_pdf,
                        str(msg.chunk_path),
                        str(mineru_output_dir),
                        str(pdf_type),
                        str(mineru_api_key) if mineru_api_key else "",
                        str(mineru_base_url) if mineru_base_url else "",
                    )

                    if not result.get("success"):
                        msg.error = f"MinerU failed: {result.get('error', 'Unknown error')}"
                        logger.error(f"❌ MinerU 失败: {msg.chunk_path.name} | {msg.error}")
                        return

                    msg.mineru_output = result
                    await output_queue.put(msg)
                    logger.info(f"✅ MinerU 完成: {msg.chunk_path.name}")

                except Exception as e:
                    msg.error = f"MinerU exception: {e}"
                    logger.error(f"❌ MinerU 异常: {msg.chunk_path.name} | {e}")
                finally:
                    input_queue.task_done()

        while not end_signal_received:
            msg = await input_queue.get()
            if msg is None:
                input_queue.task_done()
                end_signal_received = True
                break
            task = asyncio.create_task(process(msg))
            running_tasks.append(task)

        await input_queue.join()

        if running_tasks:
            await asyncio.gather(*running_tasks, return_exceptions=True)

        await output_queue.put(None)
        logger.info("✅ MinerU 处理阶段完成")

    finally:
        if api_process is not None:
            logger.info("🛑 关闭 MinerU API 服务...")
            api_process.terminate()
            try:
                api_process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                api_process.kill()
                logger.warning("⚠️ MinerU API 进程强制终止")