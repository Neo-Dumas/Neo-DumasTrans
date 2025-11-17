# core/pdf_preprocessor.py

import fitz  # PyMuPDF
from pathlib import Path
from pypdf import PdfReader, PdfWriter
from loguru import logger


def adjust_page_boxes_to_medibox(input_path: Path, output_path: Path):
    """将 PDF 每页的 CropBox 设置为等于 MediaBox"""
    doc = fitz.open(str(input_path))
    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        page.set_cropbox(page.mediabox)
    doc.save(str(output_path))
    doc.close()
    logger.info(f"✅ 已调整所有页面的 CropBox 以匹配 MediaBox，并保存到 {output_path}")


def preprocess_and_split_pdf(
    input_pdf: Path,
    workdir: Path,
    chunk_size: int,
) -> list[Path]:
    """
    对 PDF 强制进行 CropBox=MediaBox 预处理（保留完整扫描内容），
    然后分割成多个 chunk。文件名截取原 stem 前10个字符以避免路径过长。
    返回所有 chunk 的路径列表。
    """
    chunks_dir = workdir / "chunks"
    chunks_dir.mkdir(exist_ok=True)

    # 强制预处理：统一 CropBox 为 MediaBox
    short_name = input_pdf.stem[:10]  # 截断至最多10个字符
    processed_pdf = workdir / f"{short_name}.pdf"
    adjust_page_boxes_to_medibox(input_pdf, processed_pdf)

    # 分割预处理后的 PDF
    reader = PdfReader(str(processed_pdf))
    total_pages = len(reader.pages)
    base_name = processed_pdf.stem
    chunk_paths = []

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

        chunk_paths.append(chunk_file)
        logger.info(f"✂️ 分割完成: {chunk_file.name}")

    logger.info("✅ 预处理与分割阶段完成")
    return chunk_paths