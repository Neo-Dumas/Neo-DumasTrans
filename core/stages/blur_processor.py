import asyncio
from pathlib import Path
from loguru import logger
from ..pipeline_message import PipelineMessage
from ..blur_pdf_from_translated import generate_censored_pdf


async def stage_blur_processor(
    input_queue: asyncio.Queue,
    output_queue: asyncio.Queue
):
    """
    Stage 4.5: 为每个 chunk 生成涂白 PDF（_censored.pdf）
    """
    end_signal_received = False
    
    while not end_signal_received:
        msg: PipelineMessage = await input_queue.get()
        if msg is None:
            input_queue.task_done()
            end_signal_received = True
            break

        if msg.error:
            input_queue.task_done()
            continue

        origin_pdf = msg.chunk_path
        translated_json = msg.translated_path
        censored_pdf = msg.translated_path.parent / f"{msg.chunk_stem}_censored.pdf"

        # 跳过逻辑：如果涂白 PDF 已存在，直接跳过
        if censored_pdf.exists():
            msg.censored_pdf_path = censored_pdf
            await output_queue.put(msg)
            logger.info(f"🩹 涂白PDF已存在，跳过处理: {censored_pdf.name}")
            input_queue.task_done()
            continue

        if not origin_pdf.exists():
            msg.error = f"原始 PDF 文件不存在: {origin_pdf}"
            logger.error(f"❌ 涂白失败: {msg.error}")
            input_queue.task_done()
            continue

        if not translated_json or not translated_json.exists():
            msg.error = f"叶块文件不存在: {translated_json}"
            logger.error(f"❌ 涂白失败: {msg.translated_json}")
            input_queue.task_done()
            continue

        try:
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                None,
                generate_censored_pdf,
                translated_json,
                origin_pdf,
                censored_pdf
            )

            if result["success"] and censored_pdf.exists():
                msg.censored_pdf_path = censored_pdf
                await output_queue.put(msg)
                logger.info(f"🩹 涂白完成: {censored_pdf.name}")
            else:
                msg.error = f"涂白失败: {result.get('error', '未知错误')}"
                logger.error(f"❌ 涂白失败: {msg.error}")

        except Exception as e:
            msg.error = f"涂白过程发生异常: {e}"
            logger.error(f"❌ 涂白异常: {msg.error}")

        input_queue.task_done()

    await output_queue.put(None)
    logger.info("✅ 涂白处理阶段完成")