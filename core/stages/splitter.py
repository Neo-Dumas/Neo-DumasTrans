# core/stages/splitter.py

import asyncio
from pathlib import Path
from loguru import logger
from ..pdf_preprocessor import preprocess_and_split_pdf
from ..pipeline_message import PipelineMessage


async def stage_splitter(
    pdf_path: Path,
    workdir: Path,
    chunk_size: int,
    output_queue: asyncio.Queue,
    pdf_type: str
):
    """
    Stage 1: 调用专用预处理+分割模块，发送每个 chunk。
    """
    loop = asyncio.get_running_loop()
    chunk_paths = await loop.run_in_executor(
        None,
        preprocess_and_split_pdf,
        pdf_path,
        workdir,
        chunk_size
    )

    total_chunks = len(chunk_paths)
    logger.info(f"✂️ PDF 分割完成，共生成 {total_chunks} 个 chunk")

    for chunk_path in chunk_paths:
        msg = PipelineMessage(chunk_path)
        msg.pdf_type = pdf_type
        msg.total_chunks = total_chunks  # ←←← 关键：设置共享总数
        await output_queue.put(msg)

    logger.info("✅ 分割阶段完成")
    await output_queue.put(None)  # 发送结束信号