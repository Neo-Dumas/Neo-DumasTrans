# core/pdf_final_merger.py

"""
独立工具：仅使用 fitz 合并 PDF 并保留书签（不再压缩）。
"""

from pathlib import Path
import fitz  # PyMuPDF
from loguru import logger


def _outline_to_list(doc: fitz.Document):
    try:
        toc = doc.get_toc()
        if not toc:
            return []
        result = []
        for entry in toc:
            if not isinstance(entry, (list, tuple)) or len(entry) < 3:
                logger.debug(f"跳过无效书签项: {entry}")
                continue
            level = int(entry[0])
            title = str(entry[1]).strip()
            page = int(entry[2])  # 1-based
            result.append([level, title, page])
        return result
    except Exception as e:
        logger.warning(f"⚠️ 提取书签失败: {e}")
        return []


def _adjust_outline_page_numbers(outline, page_offset):
    if not outline:
        return []
    if not isinstance(outline, list):
        logger.warning(f"_outline 不是 list 类型，跳过处理: {type(outline)} = {outline}")
        return []

    result = []
    for item in outline:
        if not isinstance(item, list) or len(item) < 3:
            logger.warning(f"书签项格式无效，跳过: {item}")
            continue

        new_item = item.copy()
        if isinstance(new_item[2], int):
            new_item[2] += page_offset  # 转为新文档中的 1-based 页码
        else:
            logger.debug(f"书签页码非整数，保留原值: {new_item[2]}")

        result.append(new_item)
    return result


def merge_all_final_pdfs(
    file_list: list,
    output_path: str = None,
    output_filename: str = "all_merged_output.pdf",
) -> dict:
    """
    仅使用 fitz 合并 PDF 并保留书签（不进行压缩）。
    """
    if not file_list:
        error_msg = "文件列表为空，无可合并的 PDF 文件"
        logger.error(error_msg)
        return {
            "success": False,
            "output_path": None,
            "merged_count": 0,
            "error": error_msg,
            "used_fitz": True,
            "compressed": False,
        }

    # 验证并收集有效 PDF 文件
    final_pdfs = []
    for fp in file_list:
        path = Path(fp)
        if path.is_file() and path.suffix.lower() == ".pdf":
            final_pdfs.append(path.resolve())
        else:
            logger.warning(f"🟡 跳过无效或非PDF文件: {fp}")

    if not final_pdfs:
        error_msg = "未找到任何有效的 PDF 文件进行合并"
        logger.error(error_msg)
        return {
            "success": False,
            "output_path": None,
            "merged_count": 0,
            "error": error_msg,
            "used_fitz": True,
            "compressed": False,
        }

    final_pdfs.sort(key=lambda p: p.name)
    merged_count = len(final_pdfs)
    logger.info(f"🔍 准备合并 {merged_count} 个 PDF 文件")

    # 确定输出路径
    if output_path:
        final_output_path = Path(output_path).resolve()
    else:
        final_output_path = (final_pdfs[0].parent / output_filename).resolve()

    final_output_path.parent.mkdir(parents=True, exist_ok=True)

    # === 使用 fitz 合并（唯一方式）===
    try:
        logger.info("📚 使用 fitz 合并 PDF 并尝试保留书签...")
        merged_doc = fitz.open()
        total_pages = 0
        all_outlines = []

        for pdf_path in final_pdfs:
            with fitz.open(pdf_path) as src:
                # 提取书签
                outline_list = _outline_to_list(src)

                doc_info = {
                    "path": str(pdf_path),
                    "page_count": len(src),
                    "is_encrypted": src.is_encrypted,
                    "outline_count": len(outline_list),
                }
                logger.debug(f"📄 PDF 结构分析: {doc_info}")

                start_page_0based = total_pages
                merged_doc.insert_pdf(src)

                if outline_list:
                    adjusted = _adjust_outline_page_numbers(outline_list, start_page_0based)
                    all_outlines.extend(adjusted)
                    logger.debug(f"   ✅ 提取并调整 {len(adjusted)} 个书签")
                else:
                    logger.debug(f"   ❌ 无有效书签")

                total_pages += len(src)

        # 写入书签（如有）
        if all_outlines:
            try:
                merged_doc.set_toc(all_outlines)
                logger.info(f"🔖 已写入 {len(all_outlines)} 个书签")
            except Exception as e_toc:
                logger.warning(f"⚠️ 书签写入失败（继续保存无书签文件）: {e_toc}")
        else:
            logger.info("📭 无书签可写入")

        # 直接保存最终文件（不再压缩）
        merged_doc.save(str(final_output_path))
        merged_doc.close()

        logger.success(f"✅ 合并完成 → {final_output_path}")

        return {
            "success": True,
            "output_path": str(final_output_path),
            "merged_count": merged_count,
            "error": None,
            "used_fitz": True,
            "compressed": False,  # 明确标记未压缩
        }

    except Exception as e_fitz:
        logger.error(f"❌ fitz 合并失败: {e_fitz}", exc_info=True)
        return {
            "success": False,
            "output_path": None,
            "merged_count": 0,
            "error": str(e_fitz),
            "used_fitz": True,
            "compressed": False,
        }