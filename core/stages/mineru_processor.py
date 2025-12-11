
# core/stages/mineru_processor.py
import torch
import os
import subprocess
import asyncio
from pathlib import Path
from typing import Optional, List
from loguru import logger
from ..pipeline_message import PipelineMessage
from ..mineru_engine import run_single_pdf

# 硬编码 MinerU API 可执行文件的相对路径（相对于项目根目录）
MINERU_API_EXE = "python-3.10.11/Scripts/mineru-api.exe"


def _is_successfully_processed(stem: str, output_dir: Path, mode: str) -> bool:
    """检查是否已成功生成中间 JSON 文件"""
    middle_json_path = output_dir / stem / mode / f"{stem}_middle.json"
    return middle_json_path.exists() and middle_json_path.stat().st_size > 0


def _build_skipped_result(stem: str, output_dir: Path, mode: str) -> dict:
    """构建跳过时的成功结果（与 engine 一致）"""
    middle_json_path = output_dir / stem / mode / f"{stem}_middle.json"
    logger.info(f"⏭️  Skipping {stem} (already processed)")
    return {
        "success": True,
        "error": "",
        "output_path": str(middle_json_path)
    }


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


def _detect_gpu_and_set_env(pdf_type: str) -> dict:
    """自动检测 GPU 并返回合适的环境变量字典，根据 pdf_type 决定是否限制显存"""
    env = os.environ.copy()
    if torch.cuda.is_available():
        total_vram_gb = torch.cuda.get_device_properties(0).total_memory / (1024 ** 3)
        if pdf_type in ("txt", "ocr"):
            reserved_for_translation = 7  # 预留 7GB 给翻译模块
            allowed_vram = max(1, int(total_vram_gb - reserved_for_translation))
            env["MINERU_DEVICE_MODE"] = "cuda:0"
            env["MINERU_VIRTUAL_VRAM_SIZE"] = str(allowed_vram)
            logger.info(f"🎮 检测到 GPU，总显存: {total_vram_gb:.1f}GB，MinerU(txt/ocr) 限制使用: {allowed_vram}GB")
        else:  # vlm 本地模式
            allowed_vram = int(total_vram_gb)  # 不预留，全给 VLM
            env["MINERU_DEVICE_MODE"] = "cuda:0"
            env["MINERU_VIRTUAL_VRAM_SIZE"] = str(allowed_vram)
            logger.info(f"🎮 检测到 GPU，总显存: {total_vram_gb:.1f}GB，MinerU(vlm本地) 使用全部显存")
    else:
        env["MINERU_DEVICE_MODE"] = "cpu"
        logger.info("🖥️ 未检测到 CUDA GPU，回退到 CPU 模式")
    return env


def _start_mineru_api(env: dict) -> subprocess.Popen:
    """启动 MinerU API 子进程"""
    exe_path = Path(MINERU_API_EXE)
    logger.info("🚀 启动 MinerU API 服务...")
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
    """处理单个消息 —— 不再包含跳过逻辑，只负责实际调用引擎"""
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


async def stage_mineru_processor(
    input_queue: asyncio.Queue,
    output_queue: asyncio.Queue,
    mineru_output_dir: Path,
    pdf_type: str,
    concurrency: int,
    mineru_api_key: Optional[str] = None,
    mineru_base_url: Optional[str] = None,
):
    """
    MinerU 处理阶段：
      - 先拉取全部输入消息；
      - 统一跳过已处理文件；
      - 启动本地 API 的条件：
          * txt/ocr：总是启动；
          * vlm：仅当 mineru_api_key 为空（None 或 ""）时启动（视为本地模型）；
      - 显存策略：
          * txt/ocr：限制显存（预留 7GB）；
          * vlm 本地：不限制显存；
      - vlm 远程（api_key 非空）：不启动本地 API。
    """
    api_process = None

    # ==============================
    # 1. 拉取全部输入消息（含结束信号）
    # ==============================
    messages: List[PipelineMessage] = []
    while True:
        msg = await input_queue.get()
        input_queue.task_done()
        if msg is None:
            break
        messages.append(msg)

    if not messages:
        await output_queue.put(None)
        logger.info("✅ MinerU 阶段完成：无输入文件")
        return

    # ==============================
    # 2. 统一跳过：分离“需处理”和“已处理”
    # ==============================
    to_process: List[PipelineMessage] = []
    skipped_count = 0

    for msg in messages:
        stem = msg.chunk_path.stem
        if _is_successfully_processed(stem, mineru_output_dir, pdf_type):
            # 直接构造跳过结果并输出
            result = _build_skipped_result(stem, mineru_output_dir, pdf_type)
            msg.mineru_output = result
            await output_queue.put(msg)
            skipped_count += 1
        else:
            to_process.append(msg)

    logger.info(f"⏭️  跳过 {skipped_count} 个已处理文件，剩余 {len(to_process)} 个需处理")

    # 如果全部跳过，直接结束
    if not to_process:
        await output_queue.put(None)
        logger.info("✅ MinerU 阶段完成：所有文件均已处理")
        return

    # ==============================
    # 3. 判断是否需要启动本地 MinerU API
    # ==============================
    # 启动条件：
    #   - txt/ocr：总是启动
    #   - vlm：仅当 mineru_api_key 为空（None 或 ""）时启动（本地模型）
    need_local_api = (
        pdf_type in ("txt", "ocr") or
        (pdf_type == "vlm" and not mineru_api_key)
    )

    if need_local_api:
        exe_path = Path(MINERU_API_EXE)
        if not exe_path.exists():
            logger.error(f"❌ MinerU API 可执行文件不存在: {exe_path.absolute()}")
            await output_queue.put(None)
            return

        env = _detect_gpu_and_set_env(pdf_type)  # 根据 pdf_type 决定显存策略
        api_process = _start_mineru_api(env)

        if not await _ensure_api_ready():
            _cleanup_api_process(api_process)
            await output_queue.put(None)
            return

    # ==============================
    # 4. 并发处理剩余文件
    # ==============================
    try:
        semaphore = asyncio.Semaphore(concurrency)
        tasks = []

        async def process_msg(msg: PipelineMessage):
            async with semaphore:
                await _process_single_message(
                    msg, mineru_output_dir, pdf_type,
                    mineru_api_key, mineru_base_url, output_queue
                )

        for msg in to_process:
            tasks.append(asyncio.create_task(process_msg(msg)))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        await output_queue.put(None)
        logger.info("✅ MinerU 处理阶段完成")

    finally:
        if api_process is not None:
            _cleanup_api_process(api_process)

