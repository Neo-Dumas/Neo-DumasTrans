#core\stages\translator.py

import asyncio
from pathlib import Path
from loguru import logger
from ..pipeline_message import PipelineMessage
from ..json_translator import translate_single_json_file


async def stage_translator(
    input_queue: asyncio.Queue,
    output_queue: asyncio.Queue,
    target_lang: str,
    api_key: str,
    base_url: str,
    model_name: str,
    concurrency: int
):
    """
    Stage 4: 翻译 _leaf_blocks.json → _translated.json
    ✅ 新增：若 _translated.json 已存在，则跳过翻译
    """
    semaphore = asyncio.Semaphore(concurrency)
    running_tasks = []
    end_signal_received = False

    async def translate(msg: PipelineMessage):
        async with semaphore:
            try:
                output_file = msg.leaf_block_path.parent / f"{msg.leaf_block_path.stem.replace('_leaf_blocks', '_translated')}.json"

                # 跳过逻辑：如果翻译结果已存在，直接复用
                if output_file.exists():
                    msg.translated_path = output_file
                    await output_queue.put(msg)
                    logger.info(f"🌐 翻译文件已存在，跳过翻译: {output_file.name}")
                    return

                translated_path = await translate_single_json_file(
                    input_path=msg.leaf_block_path,
                    output_path=output_file,
                    target_lang=target_lang,
                    api_key=api_key,
                    base_url=base_url,
                    model_name=model_name,
                    concurrency=concurrency
                )
                msg.translated_path = Path(translated_path)
                await output_queue.put(msg)
                logger.info(f"🌐 翻译完成: {output_file.name}")
            except Exception as e:
                msg.error = f"Translation failed: {e}"
                logger.error(f"❌ 翻译失败: {msg.leaf_block_path} | {e}")
            finally:
                input_queue.task_done()

    while not end_signal_received:
        msg = await input_queue.get()
        if msg is None:
            input_queue.task_done()
            end_signal_received = True
            break
        if not msg.error:
            task = asyncio.create_task(translate(msg))
            running_tasks.append(task)
        else:
            input_queue.task_done()

    # 等待所有翻译任务完成
    if running_tasks:
        await asyncio.gather(*running_tasks, return_exceptions=True)
        
    await output_queue.put(None)
    logger.info("✅ 翻译阶段完成")