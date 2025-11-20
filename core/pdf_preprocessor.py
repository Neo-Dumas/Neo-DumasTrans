# core/pdf_preprocessor.py

import subprocess
import platform
from pathlib import Path
from loguru import logger
import time
import fitz  # PyMuPDF

def rotate_pages_to_upright(input_path: Path, output_path: Path):
    """
    使用 Ghostscript 将 PDF 标准化为：
      - rotation = 0（内容 upright）
      - MediaBox = [0, 0, w, h]
      - CropBox 被对齐到 (0, 0)
      - 无负坐标、无偏移、无多余小数
      - 保留矢量内容（文字可选）
    """
    logger.info(f"🔄 [standardize] 开始标准化 PDF: {input_path}")
    logger.info(f"📤 输出路径: {output_path}")

    # === 自动定位 Ghostscript ===
    if platform.system() == "Windows":
        gs_candidates = ["gswin64c.exe", "gswin64.exe", "gs.exe"]
        gs_path = None
        for exe in gs_candidates:
            try:
                result = subprocess.run([exe, "-v"], capture_output=True, text=True, timeout=10)
                if result.returncode == 0 and "Ghostscript" in result.stdout:
                    gs_path = exe
                    break
            except (FileNotFoundError, subprocess.TimeoutExpired):
                continue

        if gs_path is None:
            local_gs = Path("gs10.06.0/bin/gswin64c.exe")
            if local_gs.exists():
                gs_path = str(local_gs.resolve())
                logger.info(f"📦 [standardize] 使用本地 Ghostscript: {gs_path}")
            else:
                raise RuntimeError(
                    "未找到 Ghostscript。请确保 gswin64c.exe 在系统 PATH 中，"
                    "或将其放在项目目录的 gs10.06.0/bin/ 下。"
                )
    else:
        gs_path = "gs"

    # === 构建 Ghostscript 命令 ===
    cmd = [
        gs_path,
        "-q",
        "-dNOPAUSE",
        "-dBATCH",
        "-sDEVICE=pdfwrite",
        "-dAutoRotatePages=/PageByPage",   # 自动 upright 内容，rotation=0
        "-dUseCropBox=true",               # 以 CropBox 为准，并平移到 (0,0)
        "-dPDFSETTINGS=/prepress",         # 高质量，保留矢量
        "-dEmbedAllFonts=true",
        "-dSubsetFonts=true",
        "-dColorImageDownsampleType=/Bicubic",
        "-dColorImageResolution=300",
        "-dGrayImageResolution=300",
        "-dMonoImageResolution=300",
        f"-sOutputFile={output_path}",
        str(input_path),
    ]

    logger.debug(f"⚙️ [standardize] 执行命令: {' '.join(cmd)}")

    # === 调用 Ghostscript ===
    try:
        start_time = time.time()
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        duration = time.time() - start_time

        if result.returncode != 0:
            logger.error(f"❌ Ghostscript 失败 (exit {result.returncode}):\n{result.stderr}")
            raise RuntimeError(f"Ghostscript 标准化失败: {result.stderr.strip()}")
        else:
            logger.info(f"✅ [standardize] 成功生成标准化 PDF，耗时: {duration:.2f}s")
    except subprocess.TimeoutExpired:
        raise RuntimeError("Ghostscript 处理超时（>600秒）")
    except Exception as e:
        raise RuntimeError(f"调用 Ghostscript 时出错: {e}")


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

    # === 标准化阶段：替换原来的 normalize_and_align_boxes ===
    rotate_pages_to_upright(input_pdf, processed_pdf)

    # === 分割阶段（保持不变）===
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