# core/image_pdf_translator.py

import asyncio
from pathlib import Path
from loguru import logger
import shutil

# 各阶段模块（注意：不再导入 stage_splitter）
from .stages.mineru_processor import stage_mineru_processor
from .stages.leaf_extractor import stage_leaf_extractor
from .stages.translator import stage_translator
from .stages.blur_processor import stage_blur_processor
from .stages.html_renderer import stage_html_renderer
from .pipeline_message import PipelineMessage

# 工具函数：用于初始分割
from .pdf_preprocessor import preprocess_and_split_pdf

# 最终合并工具
from .pdf_final_merger import merge_all_final_pdfs


async def translate_image_pdf(
    pdf_path: str,
    output_dir: str,
    target_lang: str,
    api_key: str = None,
    model_name: str = None,
    base_url: str = None,
    final_output_dir: str = None,
    max_concurrent_translate: int = 10,
    mineru_api_key=None,
    mineru_base_url=None,
    pdf_type: str = "txt",
    chunk_size: int = 25,
    max_concurrent_mineru: int = 1,
    cleanup_workdir: bool = False,
    max_retry: int = 3,
    **kwargs
):
    """
    主入口：启动可重试的流水线。
    分割只执行一次，后续失败时从 mineru 阶段重试。
    """
    pdf_path = Path(pdf_path).resolve()
    if not pdf_path.exists():
        return {"success": False, "error": f"PDF 文件不存在: {pdf_path}"}

    project_root = Path(__file__).parent.parent.resolve()
    workdir = (project_root / "workdir" / pdf_path.stem).resolve()
    workdir.mkdir(parents=True, exist_ok=True)

    final_output_path_obj = Path(final_output_dir or output_dir).resolve()
    final_output_path_obj.mkdir(parents=True, exist_ok=True)

    logger.info(f"📄 开始处理 PDF: {pdf_path.name}")
    logger.info(f"⚙️ 使用模式: {pdf_type}")

    # === Step 1: 执行一次分割（不放入流水线）===
    loop = asyncio.get_running_loop()
    try:
        chunk_paths = await loop.run_in_executor(
            None,
            preprocess_and_split_pdf,
            pdf_path,
            workdir,
            chunk_size
        )
    except Exception as e:
        logger.error(f"❌ 分割阶段异常: {e}")
        return {"success": False, "error": f"分割失败: {e}"}

    total_chunks = len(chunk_paths)
    if total_chunks == 0:
        return {"success": False, "error": "PDF 分割后无有效 chunk"}

    logger.info(f"✂️ PDF 已分割为 {total_chunks} 个 chunk，准备进入处理流水线")

    # === Step 2: 重试循环 ===
    for attempt in range(1, max_retry + 1):
        logger.info(f"🔁 第 {attempt}/{max_retry} 次尝试处理 {total_chunks} 个 chunk")

        # === 队列定义（从 mineru 开始）===
        q_mineru_to_leaf = asyncio.Queue()
        q_leaf_to_translate = asyncio.Queue()
        q_translate_to_blur = asyncio.Queue()
        q_blur_to_html = asyncio.Queue()
        q_html_to_pdf = asyncio.Queue()

        # === 构造 mineru 的输入队列（关键！）===
        q_splitter_to_mineru = asyncio.Queue()
        for chunk_path in chunk_paths:
            msg = PipelineMessage(chunk_path)
            msg.pdf_type = pdf_type
            msg.total_chunks = total_chunks  # ← 共享总数
            await q_splitter_to_mineru.put(msg)
        await q_splitter_to_mineru.put(None)  # 结束信号

        # === 启动从 mineru 到 html_renderer 的任务 ===
        tasks = [
            asyncio.create_task(stage_mineru_processor(
                q_splitter_to_mineru, q_mineru_to_leaf,
                workdir / "mineru_results", pdf_type,
                max_concurrent_mineru, mineru_api_key, mineru_base_url
            )),
            asyncio.create_task(stage_leaf_extractor(q_mineru_to_leaf, q_leaf_to_translate, pdf_type)),
            asyncio.create_task(stage_translator(
                q_leaf_to_translate, q_translate_to_blur,
                target_lang, api_key, base_url, model_name, max_concurrent_translate
            )),
            asyncio.create_task(stage_blur_processor(q_translate_to_blur, q_blur_to_html)),
            asyncio.create_task(stage_html_renderer(q_blur_to_html, q_html_to_pdf, kwargs)),
        ]

        try:
            await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            logger.warning(f"第 {attempt} 次流水线执行异常（继续重试）: {e}")

        # === 收集最终生成的 PDF 路径 ===
        final_pdfs = []
        received_stems = set()

        while not q_html_to_pdf.empty():
            try:
                msg = q_html_to_pdf.get_nowait()
                if msg is None:
                    continue
                if msg.pdf_path and Path(msg.pdf_path).is_file():
                    final_pdfs.append(str(msg.pdf_path))
                    received_stems.add(msg.chunk_stem)
            except asyncio.QueueEmpty:
                break


        actual_count = len(final_pdfs)
        logger.info(f"📊 本次尝试生成了 {actual_count} / {total_chunks} 个最终 PDF")

        if actual_count == total_chunks:
            # ✅ 数量一致，执行最终合并
            merge_result = merge_all_final_pdfs(
                file_list=final_pdfs,
                output_path=str(final_output_path_obj / f"{pdf_path.stem}_translated.pdf")
            )

            if merge_result["success"]:
                final_pdf_path = Path(merge_result["output_path"])

                if cleanup_workdir:
                    try:
                        if workdir.exists():
                            shutil.rmtree(workdir)
                            logger.info(f"🧹 工作区已清除: {workdir}")
                    except Exception as e:
                        logger.warning(f"⚠️ 清理工作区失败（但流程已成功）: {e}")
                else:
                    logger.info(f"🔍 调试模式：保留工作区 {workdir}")

                return {
                    "success": True,
                    "output_path": str(final_pdf_path),
                    "merged_pdf_path": str(final_pdf_path),
                    "message": "Pipeline completed successfully."
                }
            else:
                logger.error(f"❌ 合并失败: {merge_result['error']}")
        else:
            missing_count = total_chunks - actual_count
            logger.warning(f"🟡 缺失 {missing_count} 个 chunk 的最终 PDF，准备重试...")

        # 重试前等待（可选）
        if attempt < max_retry:
            await asyncio.sleep(1)

    # === 所有重试失败 ===
    return {
        "success": False,
        "error": f"经过 {max_retry} 次重试，仍未能生成完整的 {total_chunks} 个 PDF（最后一次仅生成 {actual_count} 个）"
    }