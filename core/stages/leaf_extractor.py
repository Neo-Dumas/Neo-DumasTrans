import asyncio
from pathlib import Path
from loguru import logger
from ..pipeline_message import PipelineMessage
from ..split_json_extractor import extract_leaf_blocks_from_file


async def stage_leaf_extractor(
    input_queue: asyncio.Queue,
    output_queue: asyncio.Queue,
    pdf_type: str
):
    """
    Stage 3: 提取叶级块（_middle.json → _leaf_blocks.json）
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

        middle_json = Path(msg.mineru_output["output_path"])
        leaf_json = middle_json.parent / f"{msg.chunk_stem}_leaf_blocks.json"

        # 跳过逻辑：如果 leaf_blocks.json 已存在，直接跳过提取
        if leaf_json.exists():
            msg.leaf_block_path = leaf_json
            await output_queue.put(msg)
            logger.info(f"🔍 叶块文件已存在，跳过提取: {leaf_json.name}")
            input_queue.task_done()
            continue

        if not middle_json.exists():
            msg.error = f"Missing _middle.json: {middle_json}"
            logger.error(f"❌ 缺失文件: {msg.error}")
            input_queue.task_done()
            continue

        try:
            loop = asyncio.get_running_loop()
            success = await loop.run_in_executor(
                None,
                extract_leaf_blocks_from_file,
                middle_json,
                pdf_type
            )

            if success:
                msg.leaf_block_path = leaf_json
                await output_queue.put(msg)
                logger.info(f"🔍 叶块提取完成: {leaf_json.name}")
            else:
                msg.error = f"Extract leaf blocks failed: {middle_json}"
                logger.error(f"❌ 叶块提取失败: {msg.error}")
        except Exception as e:
            msg.error = f"Exception during leaf extraction: {e}"
            logger.error(f"❌ 叶块提取异常: {msg.error}")

        input_queue.task_done()

    await output_queue.put(None)
    logger.info("✅ 叶块提取阶段完成")