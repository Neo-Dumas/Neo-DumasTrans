# core/stages/mineru_processor.py
import torch
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
            await asyncio.open_connection(host, port)
            return True
        except (OSError, asyncio.TimeoutError):
            await asyncio.sleep(1)
    return False


def _detect_gpu_and_set_env() -> dict:
    """自动检测 GPU 并返回合适的环境变量字典"""
    env = os.environ.copy()
    if torch.cuda.is_available():
        total_vram_gb = torch.cuda.get_device_properties(0).total_memory / (1024 ** 3)
        reserved_for_translation = 7  # 预留 7GB 给翻译模块
        allowed_vram = max(1, int(total_vram_gb - reserved_for_translation))
        env["MINERU_DEVICE_MODE"] = "cuda:0"
        env["MINERU_VIRTUAL_VRAM_SIZE"] = str(allowed_vram)
        logger.info(f"🎮 检测到 GPU，总显存: {total_vram_gb:.1f}GB，MinerU 限制使用: {allowed_vram}GB")
    else:
        env["MINERU_DEVICE_MODE"] = "cpu"
        logger.info("🖥️ 未检测到 CUDA GPU，回退到 CPU 模式")
    return env


def _start_mineru_api(env: dict) -> subprocess.Popen:
    """启动 MinerU API 子进程"""
    exe_path = Path(MINERU_API_EXE)
    logger.info("🚀 启动 MinerU API 服务 (自动选择设备，限制显存)...")
    return subprocess.Popen([
        str(exe_path), "--host", "127.0.0.1", "--port", "8000"
    ], env=env)


async def _ensure_api_ready() -> bool:
    """确保 MinerU API 在指定时间内就绪"""
    logger.info("⏳ 等待 MinerU API 端口 8000 就绪...")
    ready = await _wait_for_port("127.0.0.1", 8000, timeout=30)
    if ready:
        logger.info("✅ MinerU API 端口 8000 已就绪")
    else:
        logger.error("❌ MinerU API 端口 8000 在 30 秒内未就绪")
    return ready


def _cleanup_api_process(api_process: subprocess.Popen):
    """安全终止 MinerU API 进程"""
    if api_process is None:
        return
    logger.info("🛑 关闭 MinerU API 服务...")
    api_process.terminate()
    try:
        api_process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        api_process.kill()
        logger.warning("⚠️ MinerU API 进程强制终止")


async def _process_single_message(
    msg: PipelineMessage,
    mineru_output_dir: Path,
    pdf_type: str,
    mineru_api_key: Optional[str],
    mineru_base_url: Optional[str],
    output_queue: asyncio.Queue,
):
    """处理单个 PipelineMessage"""
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
        else:
            msg.mineru_output = result
            await output_queue.put(msg)
            logger.info(f"✅ MinerU 完成: {msg.chunk_path.name}")

    except Exception as e:
        msg.error = f"MinerU exception: {e}"
        logger.error(f"❌ MinerU 异常: {msg.chunk_path.name} | {e}")
    finally:
        # 注意：task_done 应由调用方在 queue.get() 后调用
        pass


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

    # 如果是 txt 或 ocr 类型，才需要启动本地 MinerU API
    if pdf_type in ("txt", "ocr"):
        exe_path = Path(MINERU_API_EXE)
        if not exe_path.exists():
            logger.error(f"❌ MinerU API 可执行文件不存在: {exe_path.absolute()}")
            await output_queue.put(None)
            return

        env = _detect_gpu_and_set_env()
        api_process = _start_mineru_api(env)

        if not await _ensure_api_ready():
            _cleanup_api_process(api_process)
            await output_queue.put(None)
            return

    try:
        semaphore = asyncio.Semaphore(concurrency)
        running_tasks = []
        end_signal_received = False

        async def process(msg: PipelineMessage):
            async with semaphore:
                await _process_single_message(
                    msg, mineru_output_dir, pdf_type,
                    mineru_api_key, mineru_base_url, output_queue
                )
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
            _cleanup_api_process(api_process)