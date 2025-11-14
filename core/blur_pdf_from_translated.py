import json
import logging
import subprocess
from pathlib import Path
from typing import Dict, Any
import fitz  # PyMuPDF
from core.pdf_utils import get_background_color_from_page, organize_boxes
logger = logging.getLogger(__name__)


def generate_censored_pdf(
    translated_json: Path,
    origin_pdf: Path,
    output_pdf: Path
) -> Dict[str, Any]:
    try:
        with open(translated_json, "r", encoding="utf-8") as f:
            blocks = json.load(f)

        if not isinstance(blocks, list):
            return {"success": False, "error": f"{translated_json.name}: JSON 格式错误"}

        if output_pdf.exists():
            logger.info(f"跳过生成涂白 PDF，文件已存在: {output_pdf}")
            return {"success": True}

        doc = fitz.open(origin_pdf)

        def is_code_related(block: dict) -> bool:
            code_keywords = {"code", "algorithm", "code_body", "code_caption"}
            for key in ["type", "type1", "type2", "type3"]:
                if block.get(key) in code_keywords:
                    return True
            return False

        TARGET_TYPES = {"text", "table", "interline_equation", "inline_equation"}
        page_boxes, _ = organize_boxes(blocks, TARGET_TYPES, is_code_related)

        for page_idx in range(doc.page_count):
            page = doc[page_idx]
            boxes = page_boxes.get(page_idx, [])
            
            for rect in boxes:
                page.add_redact_annot(rect)
            
            page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE)
            
            for rect in boxes:
                bg_rgb = get_background_color_from_page(page, rect)
                page.draw_rect(rect, color=bg_rgb, fill=bg_rgb)

        # 一步到位：使用最强结构优化参数
        doc.save(str(output_pdf), deflate=True, garbage=4, clean=True)
        doc.close()

        logger.info(f"✅ 已生成安全且颜色正确的脱敏 PDF: {output_pdf}")
        return {"success": True}

    except Exception as e:
        error_msg = f"处理失败: {e}"
        logger.error(f"❌ {error_msg}")
        return {"success": False, "error": error_msg}