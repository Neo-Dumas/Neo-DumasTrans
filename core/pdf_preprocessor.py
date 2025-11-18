# core/pdf_preprocessor.py

import fitz  # PyMuPDF
from pathlib import Path
from loguru import logger
import time


def normalize_and_align_boxes(input_path: Path, output_path: Path):
    logger.info(f"🔍 [normalize] 开始处理输入文件: {input_path}")
    logger.info(f"📤 输出路径: {output_path}")

    open_start = time.time()
    try:
        doc = fitz.open(str(input_path))
        open_dur = time.time() - open_start
        logger.info(f"✅ [normalize] PDF 打开成功，耗时: {open_dur:.3f}s")
    except Exception as e:
        logger.error(f"❌ [normalize] 打开 PDF 失败: {e}")
        raise

    total_pages = len(doc)
    logger.info(f"📊 [normalize] 文档总页数: {total_pages}")

    for page_num in range(total_pages):
        logger.info(f"\n{'='*70}")
        logger.info(f"📖 [normalize] 正在处理第 {page_num + 1}/{total_pages} 页")

        load_start = time.time()
        try:
            page = doc.load_page(page_num)
            load_dur = time.time() - load_start
            logger.info(f"✅ [normalize] 页面加载成功，耗时: {load_dur:.3f}s")
        except Exception as e:
            logger.error(f"❌ [normalize] 加载第 {page_num + 1} 页失败: {e}")
            continue

        # 获取原始 mediabox
        mb = page.mediabox
        x0, y0, x1, y1 = float(mb.x0), float(mb.y0), float(mb.x1), float(mb.y1)
        width, height = x1 - x0, y1 - y0
        logger.info(f"📦 [normalize] 原始 MediaBox: [{x0:.6f}, {y0:.6f}, {x1:.6f}, {y1:.6f}]")
        logger.info(f"📏 [normalize] 计算尺寸: w={width:.3f}, h={height:.3f}")

        # 防御性修复
        if width <= 0:
            width = 1.0
            logger.warning(f"⚠️ [normalize] 第 {page_num + 1} 页宽度无效，重置为 1")
        if height <= 0:
            height = 1.0
            logger.warning(f"⚠️ [normalize] 第 {page_num + 1} 页高度无效，重置为 1")

        # === 关键操作 1: set_mediabox ===
        logger.info(f"🔧 [normalize] 准备设置 MediaBox 为 [0, 0, {width:.3f}, {height:.3f}]")
        try:
            set_mb_start = time.time()
            page.set_mediabox(fitz.Rect(0, 0, width, height))
            set_mb_dur = time.time() - set_mb_start
            logger.info(f"✅ [normalize] set_mediabox 成功，耗时: {set_mb_dur:.3f}s")
        except Exception as e:
            logger.error(f"💥 [normalize] set_mediabox 失败 (页 {page_num + 1}): {e}")
            continue

        # === 关键操作 2: set_cropbox ===
        logger.info(f"🔧 [normalize] 准备设置 CropBox = MediaBox")
        try:
            set_cb_start = time.time()
            page.set_cropbox(fitz.Rect(0, 0, width, height))
            set_cb_dur = time.time() - set_cb_start
            logger.info(f"✅ [normalize] set_cropbox 成功，耗时: {set_cb_dur:.3f}s")
        except Exception as e:
            logger.error(f"💥 [normalize] set_cropbox 失败 (页 {page_num + 1}): {e}")
            continue

        logger.info(f"🎉 [normalize] 第 {page_num + 1} 页处理完成")

    # === 保存阶段 ===
    logger.info(f"\n💾 [normalize] 准备保存处理后的 PDF 到 {output_path}")
    try:
        save_start = time.time()
        doc.save(str(output_path), garbage=4, deflate=True)
        save_dur = time.time() - save_start
        logger.info(f"✅ [normalize] 保存成功，耗时: {save_dur:.3f}s")
    except Exception as e:
        logger.error(f"❌ [normalize] 保存失败: {e}")
        raise
    finally:
        close_start = time.time()
        doc.close()
        close_dur = time.time() - close_start
        logger.info(f"🔒 [normalize] 文档已关闭，耗时: {close_dur:.3f}s")

    logger.info(f"✅ [normalize] 全流程完成")


def preprocess_and_split_pdf(
    input_pdf: Path,
    workdir: Path,
    chunk_size: int,
) -> list[Path]:
    chunks_dir = workdir / "chunks"
    chunks_dir.mkdir(exist_ok=True)
    logger.info(f"📁 创建/确认 chunks 目录: {chunks_dir}")

    short_name = input_pdf.stem[:10]
    processed_pdf = workdir / f"{short_name}.pdf"
    logger.info(f"⚙️ 启动预处理: {input_pdf} → {processed_pdf}")

    # === 预处理阶段 ===
    normalize_and_align_boxes(input_pdf, processed_pdf)

    # === 分割阶段 ===
    logger.info(f"\n✂️ [split] 开始分割 PDF: {processed_pdf}")
    split_open_start = time.time()
    try:
        src_doc = fitz.open(str(processed_pdf))
        split_open_dur = time.time() - split_open_start
        logger.info(f"✅ [split] 分割源文档打开成功，耗时: {split_open_dur:.3f}s")
    except Exception as e:
        logger.error(f"❌ [split] 无法打开预处理后的 PDF: {e}")
        raise

    total_pages = len(src_doc)
    logger.info(f"📊 [split] 预处理后共 {total_pages} 页")
    base_name = processed_pdf.stem
    chunk_paths = []

    for i in range(0, total_pages, chunk_size):
        start = i
        end = min(i + chunk_size, total_pages) - 1  # fitz 的 to_page 是 inclusive
        chunk_file = chunks_dir / f"{base_name}_part_{(i // chunk_size) + 1:03d}.pdf"

        logger.info(f"\n📄 [split] 准备分割 chunk: 页 {start+1} ~ {end+1} → {chunk_file.name}")

        if not chunk_file.exists():
            logger.info(f"🆕 [split] 文件不存在，开始创建新 chunk")
            try:
                new_doc = fitz.open()
                logger.info(f"🔧 [split] 调用 insert_pdf(from_page={start}, to_page={end})")
                insert_start = time.time()
                new_doc.insert_pdf(src_doc, from_page=start, to_page=end)
                insert_dur = time.time() - insert_start
                logger.info(f"✅ [split] insert_pdf 成功，耗时: {insert_dur:.3f}s")

                save_chunk_start = time.time()
                new_doc.save(str(chunk_file))
                save_chunk_dur = time.time() - save_chunk_start
                logger.info(f"💾 [split] chunk 保存成功，耗时: {save_chunk_dur:.3f}s")

                new_doc.close()
                logger.info(f"🔒 [split] chunk 文档已关闭")
            except Exception as e:
                logger.error(f"💥 [split] 创建 chunk 失败: {e}")
                # 不中断，继续
        else:
            logger.info(f"⏭️ [split] chunk 已存在，跳过")

        chunk_paths.append(chunk_file)
        logger.info(f"✔️ [split] 已登记 chunk: {chunk_file.name}")

    src_doc.close()
    logger.info("✅ 预处理与分割阶段全部完成")
    return chunk_paths