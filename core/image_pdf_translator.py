# core/image_pdf_translator.py

import asyncio
from pathlib import Path
from typing import Optional
from loguru import logger
from pypdf import PdfReader, PdfWriter

# 各模块导入（保持原函数不变）
from .mineru_engine import run_single_pdf
from .split_json_extractor import extract_leaf_blocks_from_file
from .json_translator import translate_single_json_file
from .html_to_pdf_converter import convert_single_html_to_pdf
from .blur_pdf_from_translated import generate_censored_pdf
from .pdf_final_merger import merge_all_final_pdfs
from .json_to_html_renderer import render_json_to_html
from core.pdf_compression import compress_pdf_structure_only

class PipelineMessage:
    def __init__(self, chunk_path: Path):
        self.chunk_path = chunk_path
        self.chunk_stem = chunk_path.stem
        self.pdf_type: Optional[str] = None
        self.mineru_output: Optional[dict] = None
        self.leaf_block_path: Optional[Path] = None
        self.translated_path: Optional[Path] = None
        self.html_path: Optional[Path] = None
        self.pdf_path: Optional[Path] = None          # 用于最终翻译 PDF
        self.censored_pdf_path: Optional[Path] = None  # ✅ 新增：涂白后的 PDF 路径
        self.error: Optional[str] = None


async def stage_splitter(
    pdf_path: Path,
    workdir: Path,
    chunk_size: int,
    output_queue: asyncio.Queue,
    pdf_type: str
):
    """
    Stage 1: 分割 PDF，每生成一个 chunk 就发送消息。
    """
    chunks_dir = workdir / "chunks"
    chunks_dir.mkdir(exist_ok=True)
    reader = PdfReader(str(pdf_path))
    total_pages = len(reader.pages)
    base_name = pdf_path.stem

    for i in range(0, total_pages, chunk_size):
        start = i
        end = min(i + chunk_size, total_pages)
        chunk_file = chunks_dir / f"{base_name}_part_{(i // chunk_size) + 1:03d}.pdf"

        if not chunk_file.exists():
            writer = PdfWriter()
            for page_idx in range(start, end):
                writer.add_page(reader.pages[page_idx])
            with open(chunk_file, "wb") as f:
                writer.write(f)

        msg = PipelineMessage(chunk_file)
        msg.pdf_type = pdf_type
        await output_queue.put(msg)
        logger.info(f"✂️ 分割完成: {chunk_file.name}")

    logger.info("✅ 分割阶段完成")
    await output_queue.put(None)  # 发送结束信号


async def stage_mineru_processor(
    input_queue: asyncio.Queue,
    output_queue: asyncio.Queue,
    mineru_output_dir: Path,
    pdf_type: str,
    concurrency: int,
    mineru_api_key = None,
    mineru_base_url= None,
):
    """
    Stage 2: 并发运行 MinerU，处理每个 chunk。
    """
    semaphore = asyncio.Semaphore(concurrency)
    running_tasks = []
    end_signal_received = False

    async def process(msg: PipelineMessage):
        async with semaphore:
            try:
                # 使用线程池执行耗时的同步函数
                loop = asyncio.get_running_loop()
                result = await loop.run_in_executor(
                    None,
                    run_single_pdf,
                    str(msg.chunk_path),
                    str(mineru_output_dir),
                    str(pdf_type),                    
                    str(mineru_api_key),
                    str(mineru_base_url),  
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

    # Step 1: 消费 input_queue，创建任务
    while not end_signal_received:
        msg = await input_queue.get()
        if msg is None:
            input_queue.task_done()
            end_signal_received = True
            break
        task = asyncio.create_task(process(msg))
        running_tasks.append(task)

    # Step 2: 等待所有消息处理完成（所有 task 启动完毕）
    await input_queue.join()

    # Step 3: 等待所有已创建的任务真正执行完毕
    if running_tasks:
        await asyncio.gather(*running_tasks, return_exceptions=True)

    # Step 4: 发送结束信号
    await output_queue.put(None)
    logger.info("✅ MinerU 处理阶段完成")


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

        # ✅ 跳过逻辑：如果 leaf_blocks.json 已存在，直接跳过提取
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

                # ✅ 跳过逻辑：如果翻译结果已存在，直接复用
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

        # ✅ 跳过逻辑：如果涂白 PDF 已存在，直接跳过
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


async def _render_single_html_async(translated_json: Path, html_output: Path) -> bool:
    """异步包装 HTML 渲染"""
    loop = asyncio.get_running_loop()
    try:
        # 注意：这里传入的是函数 + 参数，不是调用结果
        result = await loop.run_in_executor(
            None,
            render_json_to_html,  # 来自 json_to_html_renderer
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
            # === 【新增】在最开始检查最终 PDF 是否已存在 ===
            html_dir = msg.translated_path.parent / "images"
            final_pdf_path = html_dir / f"{msg.chunk_stem}_rendered_translate_final.pdf"

            if final_pdf_path.exists():
                logger.info(f"🖨️ 最终PDF已存在，完全跳过处理: {final_pdf_path.name}")
                msg.pdf_path = final_pdf_path
                await output_queue.put(msg)
                input_queue.task_done()
                continue

            # —————— 以下为原有逻辑（仅当最终 PDF 不存在时才执行） ——————

            html_dir = msg.translated_path.parent / "images"
            html_dir.mkdir(exist_ok=True)
            html_file = html_dir / f"{msg.chunk_stem}_rendered.html"

            # 渲染 HTML（如果不存在）
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


async def stage_final_merger(
    input_queue: asyncio.Queue,
    final_output_dir: Path,
    pdf_stem: str
) -> Optional[Path]:
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

    # ✅ 合并 PDF（内部已包含压缩）
    result = merge_all_final_pdfs(
        file_list=[str(p) for p in pdf_paths],
        output_path=str(final_pdf)
    )

    if not result["success"]:
        logger.error(f"❌ 合并失败: {result['error']}")
        return None

    logger.success(f"🎉 最终合并与压缩完成: {final_pdf}")
    return final_pdf


async def translate_image_pdf(
    pdf_path: str,
    output_dir: str,
    target_lang: str,
    api_key: str = None,
    model_name: str = None,
    base_url: str = None,
    final_output_dir: str = None,
    max_concurrent_translate: int = 10,
    mineru_api_key = None,
    mineru_base_url= None,
    pdf_type: str = "txt",
    chunk_size: int = 25,
    max_concurrent_mineru: int = 1,
    cleanup_workdir: bool = False,  
    **kwargs
):
    """
    主入口：启动完全解耦的流水线。
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

    # === 队列定义 ===
    q_splitter_to_mineru = asyncio.Queue()
    q_mineru_to_leaf = asyncio.Queue()
    q_leaf_to_translate = asyncio.Queue()
    q_translate_to_blur = asyncio.Queue()   # 新增：翻译 → 涂白
    q_blur_to_html = asyncio.Queue()        # 新增：涂白 → HTML 渲染
    q_html_to_pdf = asyncio.Queue()
    q_pdf_to_merge = asyncio.Queue()

    # === 启动各阶段任务 ===
    tasks = [
        asyncio.create_task(stage_splitter(pdf_path, workdir, chunk_size, q_splitter_to_mineru, pdf_type)),
        asyncio.create_task(stage_mineru_processor(q_splitter_to_mineru, q_mineru_to_leaf, workdir / "mineru_results", pdf_type, max_concurrent_mineru, mineru_api_key, mineru_base_url)),
        asyncio.create_task(stage_leaf_extractor(q_mineru_to_leaf, q_leaf_to_translate, pdf_type)),
        asyncio.create_task(stage_translator(q_leaf_to_translate, q_translate_to_blur, target_lang, api_key, base_url, model_name, max_concurrent_translate)),
        asyncio.create_task(stage_blur_processor(q_translate_to_blur, q_blur_to_html)),
        asyncio.create_task(stage_html_renderer(q_blur_to_html, q_html_to_pdf, kwargs)),
        asyncio.create_task(stage_final_merger(q_html_to_pdf, final_output_path_obj, pdf_path.stem)),  # 修正：使用正确的队列
    ]

    try:
        # === 等待所有任务完成 ===
        await asyncio.gather(*tasks, return_exceptions=True)
        
        # 检查合并任务的结果
        merge_task = tasks[-1]  # 最后一个任务是合并任务
        if merge_task.done() and not merge_task.cancelled():
            final_pdf_path = merge_task.result()
        else:
            final_pdf_path = None

        # 判断是否真正成功
        if final_pdf_path and final_pdf_path.exists():
            # ✅ 成功：根据 cleanup_workdir 决定是否清理工作区
            if cleanup_workdir:
                try:
                    import shutil
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
            # ❌ 合并未生成文件，视为失败，不清理
            return {
                "success": False,
                "output_path": "",
                "error": "合并失败或最终文件未生成。"
            }
            
    except Exception as e:
        logger.error(f"Pipeline 执行异常: {e}")
        # 取消所有任务
        for task in tasks:
            if not task.done():
                task.cancel()
        # ❌ 异常视为失败，不清理工作区
        return {"success": False, "error": str(e)}