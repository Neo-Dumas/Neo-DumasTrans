# core\html_to_pdf_converter.py

"""
负责将 MinerU 生成的 textual HTML 单个文件转换为最终 PDF。
从 HTML 中动态识别 <div class="pdf-page"> 获取每页尺寸（px）→ pt，
按页分割转 PDF，合并后与涂白层叠加，并**直接压缩保存**。
"""


import shutil
from pathlib import Path
from typing import Dict, Any
from playwright.async_api import async_playwright
import fitz  # PyMuPDF
from loguru import logger


async def convert_single_html_to_pdf(
    html_file_path: str,
    censored_pdf_path: str,
    pdf_suffix: str = "_translate.pdf",
    prefer_css_page_size: bool = True,
    print_background: bool = True,
    scale: float = 1.0,
    stability_timeout: float = 10000,
    page_stable_check_interval: float = 300,
    margin: Dict[str, str] = None,
) -> Dict[str, Any]:

    html_path = Path(html_file_path)
    if not html_path.exists():
        return {"success": False, "error": f"HTML 文件不存在: {html_file_path}", "converted": []}
    if not html_path.suffix.lower() == ".html":
        return {"success": False, "error": f"不是有效的 HTML 文件: {html_file_path}", "converted": []}

    logger.info(f"📄 开始处理单个 HTML 文件: {html_path.name}")

    converted = []
    errors = []
    final_output_path = html_path.parent / f"{html_path.stem}{pdf_suffix.replace('.pdf', '_final.pdf')}"

    if final_output_path.exists():
        logger.info(f"⏭️ 跳过已存在的最终文件: {final_output_path}")
        return {"success": True, "errors": [], "converted": [str(final_output_path)]}

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(java_script_enabled=True)
            logger.success("🚀 Playwright 浏览器启动成功")

            try:
                logger.info(f"📄 处理: {html_path.name}")
                temp_dir = html_path.parent / f"{html_path.stem}_split_pages"
                temp_dir.mkdir(exist_ok=True)

                page = await context.new_page()
                file_url = html_path.resolve().absolute().as_uri()
                await page.goto(file_url, wait_until="networkidle")
                await page.wait_for_timeout(500)

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

                page_boxes = await page.evaluate('''() => {
                    return Array.from(document.querySelectorAll('.pdf-page'))
                        .map(div => ({ width: div.offsetWidth, height: div.offsetHeight }));
                }''')

                if not page_boxes:
                    raise ValueError("未找到任何 .pdf-page 元素")

                logger.info(f"📑 识别到 {len(page_boxes)} 页")

                single_pdf_paths = []
                for idx, box in enumerate(page_boxes):
                    width_px = box['width']
                    height_px = box['height']
                    width_pt = width_px * 72 / 96
                    height_pt = height_px * 72 / 96

                    await page.evaluate(f'''
                        () => {{
                            document.querySelectorAll('.pdf-page').forEach((div, i) => {{
                                div.style.display = i === {idx} ? 'block' : 'none';
                            }});
                            document.body.style.overflow = 'visible';
                            document.body.style.width = '{width_px}px';
                            document.body.style.height = '{height_px}px';
                        }}
                    ''')

                    await page.set_viewport_size({"width": int(width_px), "height": int(height_px * 1.2)})

                    await page.evaluate(f'''
                    () => {{
                        const style = document.createElement('style');
                        style.id = 'dynamic-page-size';
                        style.innerHTML = `
                            @page {{ size: {width_pt}pt {height_pt}pt; margin: 0; background: transparent; }}
                            @media print {{ @page {{ size: {width_pt}pt {height_pt}pt; margin: 0; background: transparent; }} }}
                            body, html {{ width: {width_px}px !important; height: {height_px}px !important; margin: 0 !important; padding: 0 !important; background: transparent !important; }}
                            .pdf-page {{ background: transparent !important; }}
                        `;
                        document.getElementById('dynamic-page-size')?.remove();
                        document.head.appendChild(style);
                    }}
                    ''')

                    single_pdf_path = temp_dir / f"page_{idx + 1:03d}.pdf"
                    await page.pdf(
                        path=str(single_pdf_path),
                        prefer_css_page_size=prefer_css_page_size,
                        print_background=print_background,
                        scale=scale,
                        margin={"top": "0", "right": "0", "bottom": "0", "left": "0"},
                        landscape=(width_pt > height_pt)
                    )
                    single_pdf_paths.append(str(single_pdf_path))
                    logger.debug(f"📄 已生成第 {idx + 1} 页 PDF")

                await page.close()

                # 合并单页 PDF
                merged_doc = fitz.open()
                for pdf_path in single_pdf_paths:
                    try:
                        src = fitz.open(pdf_path)
                        merged_doc.insert_pdf(src, from_page=0, to_page=0)
                        src.close()
                    except Exception as e:
                        logger.warning(f"🟡 跳过无效页: {pdf_path} - {e}")
                temp_merged_path = html_path.parent / f"{html_path.stem}{pdf_suffix}"
                merged_doc.save(str(temp_merged_path))
                merged_doc.close()
                logger.success(f"✅ 合并中间 PDF: {temp_merged_path}")

                # >>>>>>>>>> 核心：合并涂白层 + 翻译层，并直接压缩保存 <<<<<<<<<<
                output_doc = fitz.open()
                censored_path = Path(censored_pdf_path)

                try:
                    if not censored_path.exists():
                        logger.warning(f"🟡 无涂白文件，仅使用翻译内容")
                        src_doc = fitz.open(str(temp_merged_path))
                        for i in range(len(src_doc)):
                            p = src_doc[i]
                            output_doc.new_page(width=p.rect.width, height=p.rect.height).show_pdf_page(p.rect, src_doc, i)
                        src_doc.close()
                    else:
                        doc_censored = fitz.open(str(censored_path))
                        doc_translate = fitz.open(str(temp_merged_path))

                        if len(doc_censored) == len(doc_translate):
                            for i in range(len(doc_censored)):
                                base = doc_censored[i]
                                new_page = output_doc.new_page(width=base.rect.width, height=base.rect.height)
                                new_page.show_pdf_page(new_page.rect, doc_censored, i)
                                new_page.show_pdf_page(new_page.rect, doc_translate, i)
                            output_doc.set_toc(doc_censored.get_toc())
                            doc_censored.close()
                        else:
                            logger.error("❌ 页数不匹配，仅保留翻译层")
                            for i in range(len(doc_translate)):
                                p = doc_translate[i]
                                output_doc.new_page(width=p.rect.width, height=p.rect.height).show_pdf_page(p.rect, doc_translate, i)
                        doc_translate.close()

                    # ✅ 直接压缩保存最终文件（一次到位！）
                    output_doc.save(
                        str(final_output_path),
                        garbage=4,
                        deflate=True,
                        deflate_images=False,
                        clean=True
                    )
                    logger.success(f"✅ 最终 PDF 已生成并压缩: {final_output_path}")

                except Exception as e:
                    logger.exception(f"❌ 合并/保存阶段异常: {e}")
                    errors.append(f"合并保存失败: {e}")
                    # 降级：直接压缩保存翻译 PDF
                    try:
                        fallback = fitz.open(str(temp_merged_path))
                        fallback.save(
                            str(final_output_path),
                            garbage=4,
                            deflate=True,
                            deflate_images=False,
                            clean=True
                        )
                        fallback.close()
                        logger.warning(f"⚠️ 降级成功: {final_output_path}")
                    except Exception as fe:
                        logger.error(f"❌ 降级也失败: {fe}")
                        errors.append(f"降级保存失败: {fe}")
                finally:
                    output_doc.close()

                # 清理
                if temp_merged_path.exists():
                    temp_merged_path.unlink()
                shutil.rmtree(temp_dir, ignore_errors=True)

            except Exception as e:
                err_msg = f"{html_path.name}: 转换失败: {e}"
                logger.exception(f"❌ {err_msg}")
                errors.append(err_msg)

            finally:
                await browser.close()
                logger.success("🎉 Playwright 浏览器已关闭")

    except Exception as e:
        err_msg = f"Playwright 启动失败: {e}"
        logger.exception(f"❌ {err_msg}")
        errors.append(err_msg)

    # 👇 确保 converted 正确反映结果
    if final_output_path.exists():
        converted.append(str(final_output_path))

    success = len(errors) == 0
    if success:
        logger.info(f"✅ 转换完成！输出: {converted}")
    else:
        logger.warning(f"⚠️ 转换完成但有 {len(errors)} 个错误")

    return {
        "success": success,
        "errors": errors,
        "converted": converted
    }