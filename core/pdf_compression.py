# core/pdf_compression.py

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def compress_pdf_structure_only(pdf_path: Path) -> bool:
    """
    使用 PyMuPDF (fitz) 对 PDF 进行结构级瘦身：
    - 压缩文本、矢量图形、字体描述符等非图像流（Flate 压缩）
    - 清理无引用对象（garbage=4）
    - 合并重复资源（clean=True）
    - 完全保留原始图像（不重编码、不降采样）
    
    适用于 HTML 生成的臃肿 PDF，安全且高效。
    """
    try:
        import fitz  # PyMuPDF
    except ImportError:
        logger.error("❌ PyMuPDF (fitz) 未安装，请运行: pip install pymupdf")
        return False

    if not pdf_path.exists():
        logger.error(f"❌ 待压缩 PDF 不存在: {pdf_path}")
        return False

    original_size = pdf_path.stat().st_size
    temp_final = pdf_path.with_suffix(".slim.pdf")

    try:
        doc = fitz.open(pdf_path)
        # 执行结构优化，但不动图像
        doc.save(
            str(temp_final),
            garbage=4,              # 最彻底回收无用对象
            deflate=True,           # 压缩可压缩流（文本/路径等）
            deflate_images=False,   # 关键：不重新压缩图像
            clean=True              # 清理冗余结构
        )
        doc.close()

        if not temp_final.exists():
            logger.error("❌ PyMuPDF 未生成输出文件")
            return False

        # 报告结果
        compressed_size = temp_final.stat().st_size
        ratio = (1 - compressed_size / original_size) * 100
        logger.info(
            f"📦 原始大小: {original_size / 1024:.1f} KB → "
            f"压缩后: {compressed_size / 1024:.1f} KB (节省 {ratio:.1f}%)"
        )

        # 原子替换原文件
        pdf_path.unlink()
        temp_final.rename(pdf_path)
        logger.info(f"✅ PDF 结构瘦身完成并覆盖: {pdf_path}")

        return True

    except Exception as e:
        logger.error(f"❌ PyMuPDF 处理失败: {e}")
        # 清理临时文件（如果存在）
        if temp_final.exists():
            try:
                temp_final.unlink()
            except Exception:
                pass
        return False