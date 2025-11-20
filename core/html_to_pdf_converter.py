# core/html_to_pdf_converter.py

"""
负责将 MinerU 生成的 textual HTML 单个文件转换为最终 PDF。
不再使用原始分块 PDF 获取页面尺寸，
而是从 HTML 中动态识别 <div class="pdf-page"> 元素获取每页尺寸（px），转换为 pt。
然后按页分割 HTML，每页独立转为 PDF，最后合并。
"""

import re
import asyncio
import shutil
from pathlib import Path
from typing import Dict, List, Tuple
from PyPDF2 import PdfMerger  # 仍用于单页合并，但最终 layer 合并改用 fitz
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
import fitz  # PyMuPDF
from loguru import logger


async def convert_single_html_to_pdf(
    html_file_path: str,
    censored_pdf_path: str,  # 新增：直接传入涂白 PDF 路径
    pdf_suffix: str = "_translate.pdf",
    prefer_css_page_size: bool = True,
    print_background: bool = True,
    scale: float = 1.0,
    stability_timeout: float = 10000,
    page_stable_check_interval: float = 300,
    margin: Dict[str, str] = None,
) -> Dict[str, any]:

    html_path = Path(html_file_path)
    if not html_path.exists():
        return {
            "success": False,
            "error": f"HTML 文件不存在: {html_file_path}",
            "converted": []
        }

    if not html_path.suffix.lower() == ".html":
        return {
            "success": False,
            "error": f"不是有效的 HTML 文件: {html_file_path}",
            "converted": []
        }

    logger.info(f"📄 开始处理单个 HTML 文件: {html_path.name}")

    converted = []
    errors = []

    # 计算输出路径
    temp_pdf_path = html_path.parent / f"{html_path.stem}{pdf_suffix}"  # _translate.pdf
    final_output_path = temp_pdf_path.with_name(temp_pdf_path.stem + "_final.pdf")

    # 检查是否已存在最终文件
    if final_output_path.exists():
        logger.info(f"⏭️ 跳过已存在的最终文件: {final_output_path}")
        return {
            "success": True,
            "errors": [],
            "converted": [str(final_output_path)]
        }

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context(java_script_enabled=True)
            logger.success("🚀 Playwright 浏览器启动成功")

            try:
                logger.info(f"📄 处理: {html_path.name}")

                # 1. 创建临时目录存放分割后的单页 HTML 和 PDF
                temp_dir = html_path.parent / f"{html_path.stem}_split_pages"
                temp_dir.mkdir(exist_ok=True)

                # 2. 使用 Playwright 加载 HTML
                page = await context.new_page()
                file_url = html_path.resolve().absolute().as_uri()
                await page.goto(file_url, wait_until="networkidle")
                await page.wait_for_timeout(500)

                # 注入稳定性检测脚本
                await page.evaluate(f'''() => {{
                    window.pageIsStable = false;
                    let stableTimeout = null;
                    const observer = new MutationObserver(() => {{
                        if (stableTimeout) clearTimeout(stableTimeout);
                        stableTimeout = setTimeout(() => {{
                            window.pageIsStable = true;
                            observer.disconnect();
                        }}, {page_stable_check_interval});
                    }});
                    observer.observe(document.body, {{
                        childList: true, subtree: true,
                        attributes: true, characterData: true
                    }});
                    setTimeout(() => {{
                        if (!window.pageIsStable) window.pageIsStable = true;
                    }}, {stability_timeout});
                }}''')

                try:
                    await page.wait_for_function("window.pageIsStable === true", timeout=stability_timeout + 2000)
                except Exception:
                    pass

                # 3. 提取所有 .pdf-page 的尺寸（px）
                page_boxes = await page.evaluate('''() => {
                    return Array.from(document.querySelectorAll('.pdf-page'))
                        .map(div => ({
                            width: div.offsetWidth,
                            height: div.offsetHeight
                        }));
                }''')

                if not page_boxes:
                    raise ValueError("未找到任何 .pdf-page 元素")

                logger.info(f"📑 识别到 {len(page_boxes)} 页")

                # 4. 确保临时目录存在（重复创建确保安全）
                temp_dir = html_path.parent / f"{html_path.stem}_split_pages"
                temp_dir.mkdir(exist_ok=True)

                # 5. 逐页显示并导出 PDF（复用原始样式，不注入任何新 CSS）
                single_pdf_paths = []
                for idx, box in enumerate(page_boxes):
                    width_px = box['width']
                    height_px = box['height']
                    width_pt = width_px * 72 / 96
                    height_pt = height_px * 72 / 96

                    # 只显示当前页，隐藏其他页
                    await page.evaluate(f'''
                        () => {{
                            document.querySelectorAll('.pdf-page').forEach((div, i) => {{
                                div.style.display = i === {idx} ? 'block' : 'none';
                            }});
                            // 可选：调整 body 大小，避免滚动条
                            document.body.style.overflow = 'hidden';
                            document.body.style.width = '{width_px}px';
                            document.body.style.height = '{height_px}px';
                        }}
                    ''')

                    # 调整 viewport 以匹配当前页
                    await page.set_viewport_size({"width": int(width_px), "height": int(height_px * 1.2)})

                    # ✅ 注入 @page 样式，确保尺寸和边距精确
                    await page.evaluate(f'''
                    () => {{
                        const style = document.createElement('style');
                        style.id = 'dynamic-page-size';
                        style.innerHTML = `
                            @page {{
                                size: {width_pt}pt {height_pt}pt;
                                margin: 0;
                                background: transparent; /* 关键：设置 @page 背景透明 */
                            }}
                            @media print {{
                                @page {{
                                    size: {width_pt}pt {height_pt}pt;
                                    margin: 0;
                                    background: transparent; /* 关键：打印模式下也透明 */
                                }}
                            }}
                            body, html {{
                                width: {width_px}px !important;
                                height: {height_px}px !important;
                                margin: 0 !important;
                                padding: 0 !important;
                                background: transparent !important; /* 关键：强制 body 背景透明 */
                                background-color: transparent !important;
                            }}
                            /* 确保 .pdf-page 容器也是透明的 */
                            .pdf-page {{
                                background: transparent !important;
                                background-color: transparent !important;
                            }}
                        `;
                        if (document.getElementById('dynamic-page-size')) {{
                            document.getElementById('dynamic-page-size').remove();
                        }}
                        document.head.appendChild(style);
                    }}
                    ''')

                    # 等待渲染
                    await page.wait_for_timeout(100)

                    # 生成单页 PDF —— 完全复用原始逻辑
                    single_pdf_path = temp_dir / f"page_{idx + 1:03d}.pdf"
                    await page.pdf(
                        path=str(single_pdf_path),
                        prefer_css_page_size=prefer_css_page_size,
                        print_background=True,
                        scale=scale,
                        margin={"top": "0", "right": "0", "bottom": "0", "left": "0"},  # 必须传！
                        landscape=(width_pt > height_pt)
                    )

                    single_pdf_paths.append(str(single_pdf_path))
                    logger.debug(f"📄 已生成第 {idx + 1} 页 PDF")

                await page.close()

                # 6. 安全合并：只取每个单页 PDF 的第一页（仍用 PyPDF2，因为只是简单拼接）
                merger = PdfMerger()
                for pdf_path in single_pdf_paths:
                    try:
                        merger.append(str(pdf_path), pages=(0, 1))  # 只取第一页
                    except Exception as e:
                        logger.warning(f"🟡 无法读取或跳过 {pdf_path}: {e}")
                        continue

                final_pdf_path = html_path.parent / f"{html_path.stem}{pdf_suffix}"
                merger.write(str(final_pdf_path))
                merger.close()

                logger.success(f"✅ 成功生成合并 PDF: {final_pdf_path}")

                # >>>>>>>>>> 新增：透明PDF与涂抹PDF的合并逻辑（改用 PyMuPDF）<<<<<<<<<<
                try:
                    if not Path(censored_pdf_path).exists():
                        logger.warning(f"🟡 未找到对应的 _censored.pdf 文件: {censored_pdf_path}")
                        converted.append(str(final_pdf_path))  # 降级使用原始透明PDF
                    else:
                        # 使用 PyMuPDF 打开两个 PDF
                        doc_censored = fitz.open(str(censored_pdf_path))
                        doc_translate = fitz.open(str(final_pdf_path))

                        if len(doc_censored) != len(doc_translate):
                            logger.error(f"❌ 页数不匹配！{final_pdf_path.name} 有 {len(doc_translate)} 页，"
                                        f"{censored_pdf_path} 有 {len(doc_censored)} 页。跳过合并。")
                            converted.append(str(final_pdf_path))
                        else:
                            output_pdf_path = final_pdf_path.with_name(final_pdf_path.stem + "_final.pdf")
                            # 创建新文档，逐页叠加
                            output_doc = fitz.open()

                            for i in range(len(doc_censored)):
                                # 获取底页（涂白）并复制
                                base_page = doc_censored[i]
                                # 创建一个与底页尺寸/旋转一致的新页
                                new_page = output_doc.new_page(
                                    width=base_page.rect.width,
                                    height=base_page.rect.height
                                )
                                # 先绘制底页内容（包括其旋转效果）
                                new_page.show_pdf_page(new_page.rect, doc_censored, i)
                                # 再叠加翻译页（自动适配坐标系，尊重各自 Rotate）
                                new_page.show_pdf_page(new_page.rect, doc_translate, i)

                            output_doc.save(str(output_pdf_path))
                            output_doc.close()
                            doc_censored.close()
                            doc_translate.close()

                            logger.success(f"🎨 成功合并透明翻译层与涂抹层（PyMuPDF），输出: {output_pdf_path}")
                            converted.append(str(output_pdf_path))

                except Exception as merge_err:
                    logger.error(f"❌ 合并过程失败: {merge_err}")
                    errors.append(f"合并失败 {final_pdf_path}: {str(merge_err)}")
                    # 💡 兜底：使用已生成的透明翻译 PDF 作为最终输出
                    logger.warning("⚠️ 合并失败，降级使用透明翻译 PDF 作为输出")
                    converted.append(str(final_pdf_path))
                # <<<<<<<<<< 新增逻辑结束 >>>>>>>>>>

            except Exception as e:
                err_msg = f"{html_path.name}: 转换失败: {str(e)}"
                logger.error(f"❌ {err_msg}")
                errors.append(err_msg)

            finally:
                await browser.close()
                logger.success("🎉 Playwright 浏览器已关闭")

    except Exception as e:
        err_msg = f"Playwright 启动或运行失败: {str(e)}"
        logger.exception(f"❌ {err_msg}")
        errors.append(err_msg)

    # 返回结果
    success = len(errors) == 0
    if success:
        logger.info(f"✅ 单文件转换完成！输出: {converted}")
    else:
        logger.warning(f"⚠️ 转换完成，但有 {len(errors)} 个错误")

    return {
        "success": success,
        "errors": errors,
        "converted": converted
    }