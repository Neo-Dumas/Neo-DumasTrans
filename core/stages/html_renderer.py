import asyncio
from pathlib import Path
from loguru import logger
from ..pipeline_message import PipelineMessage
from ..json_to_html_renderer import render_json_to_html
from ..pdf_compression import compress_pdf_structure_only


async def _render_single_html_async(translated_json: Path, html_output: Path) -> bool:
    """异步包装 HTML 渲染"""
    loop = asyncio.get_running_loop()
    try:
        result = await loop.run_in_executor(
            None,
            render_json_to_html,
            str(translated_json),
            str(html_output)
        )
        return result.get("success", False)
    except Exception as e:
        logger.error(f"❌ 异步渲染异常: {e}")
        return False


async def stage_html_renderer(
    input_queue: asyncio.Queue,
    output_queue: asyncio.Queue,
    kwargs: dict
):
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

        try:
            # 检查最终 PDF 是否已存在
            html_dir = msg.translated_path.parent / "images"
            final_pdf_path = html_dir / f"{msg.chunk_stem}_rendered_translate_final.pdf"

            if final_pdf_path.exists():
                logger.info(f"🖨️ 最终PDF已存在，完全跳过处理: {final_pdf_path.name}")
                msg.pdf_path = final_pdf_path
                await output_queue.put(msg)
                input_queue.task_done()
                continue

            # 渲染 HTML
            html_dir.mkdir(exist_ok=True)
            html_file = html_dir / f"{msg.chunk_stem}_rendered.html"

            if html_file.exists():
                logger.info(f"📄 HTML 已存在，跳过渲染: {html_file.name}")
                msg.html_path = html_file
            else:
                if not await _render_single_html_async(msg.translated_path, html_file):
                    msg.error = f"HTML 渲染失败: {html_file}"
                    logger.error(f"❌ HTML 渲染失败: {msg.error}")
                    input_queue.task_done()
                    continue
                msg.html_path = html_file
                logger.info(f"🎨 HTML 渲染完成: {html_file.name}")

            # 准备涂白 PDF 路径
            censored_pdf_path_str = ""
            if msg.censored_pdf_path and msg.censored_pdf_path.exists():
                censored_pdf_path_str = str(msg.censored_pdf_path)
                logger.debug(f"📎 检测到涂白PDF，将用于合并: {msg.censored_pdf_path.name}")
            else:
                logger.warning(f"🟡 未找到涂白PDF文件，将跳过合并: {msg.censored_pdf_path}")

            # 转换 HTML 为 PDF（含合并）
            from ..html_to_pdf_converter import convert_single_html_to_pdf  # 延迟导入避免循环？
            pdf_result = await convert_single_html_to_pdf(
                html_file_path=str(html_file),
                censored_pdf_path=censored_pdf_path_str,
                prefer_css_page_size=kwargs.get("pdf_prefer_css_page_size", True),
                print_background=kwargs.get("print_background", True),
                scale=kwargs.get("pdf_scale", 1.0),
                stability_timeout=kwargs.get("stability_timeout", 10000),
                page_stable_check_interval=kwargs.get("page_stable_check_interval", 300),
                margin=kwargs.get("pdf_margin", {}),
            )

            if pdf_result["success"] and pdf_result["converted"]:
                final_pdf_path = Path(pdf_result["converted"][0])
                
                # 压缩 PDF
                loop = asyncio.get_running_loop()
                compression_success = await loop.run_in_executor(
                    None, compress_pdf_structure_only, final_pdf_path
                )
                if not compression_success:
                    msg.error = "PDF 压缩失败"
                    logger.error(f"❌ PDF 压缩失败: {final_pdf_path.name}")
                    input_queue.task_done()
                    continue
                
                msg.pdf_path = final_pdf_path
                await output_queue.put(msg)
                logger.info(f"🖨️✅ 最终PDF生成完成（含涂白合并）: {final_pdf_path.name}")
            else:
                error_msg = pdf_result.get("error", "未知错误")
                msg.error = f"HTML→PDF 转换失败: {error_msg}"
                logger.error(f"❌ 转换失败: {msg.error}")

        except Exception as e:
            msg.error = f"HTML渲染或PDF转换异常: {e}"
            logger.exception(f"❌ 处理失败: {msg.chunk_path.name} | {e}")

        input_queue.task_done()

    await output_queue.put(None)
    logger.info("✅ HTML渲染和PDF转换阶段完成")