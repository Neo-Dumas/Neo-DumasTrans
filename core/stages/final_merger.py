import asyncio
from pathlib import Path
from loguru import logger
from ..pipeline_message import PipelineMessage
from ..pdf_final_merger import merge_all_final_pdfs


async def stage_final_merger(
    input_queue: asyncio.Queue,
    final_output_dir: Path,
    pdf_stem: str
) -> Path | None:
    """
    Stage 7: 合并所有最终 PDF（压缩由合并函数内部完成）
    """
    pdf_paths = []
    end_signal_received = False
    
    while not end_signal_received:
        msg = await input_queue.get()
        if msg is None:
            input_queue.task_done()
            end_signal_received = True
            break
        if msg.pdf_path and msg.pdf_path.exists():
            pdf_paths.append(msg.pdf_path)
        input_queue.task_done()

    # 按名称排序确保顺序
    pdf_paths.sort(key=lambda p: p.name)

    final_pdf = final_output_dir / f"merged_{pdf_stem}.pdf"

    if not pdf_paths:
        logger.warning("⚠️ 无 PDF 文件可合并")
        return None

    # 合并 PDF（内部已包含压缩）
    result = merge_all_final_pdfs(
        file_list=[str(p) for p in pdf_paths],
        output_path=str(final_pdf)
    )

    if not result["success"]:
        logger.error(f"❌ 合并失败: {result['error']}")
        return None

    logger.success(f"🎉 最终合并与压缩完成: {final_pdf}")
    return final_pdf