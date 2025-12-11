# core/pdf_preprocessor.py
import os
import re
import subprocess
import platform
from pathlib import Path
from loguru import logger
import time
import fitz  # PyMuPDF
import concurrent.futures
from typing import Tuple, List, Optional


def sanitize_toc(toc: List[List]) -> List[List]:
    """
    清洗并修复 TOC 层级结构，并移除标题中的非法 surrogate 字符。
    """
    if not toc:
        return []

    # 移除 surrogate 的正则（U+D800–U+DFFF）
    surrogate_pattern = re.compile(r'[\ud800-\udfff]')

    def clean_title(title) -> str:
        s = str(title)
        # 移除所有孤立 surrogate
        cleaned = surrogate_pattern.sub('', s)
        # 可选：进一步替换控制字符或空标题
        if not cleaned.strip():
            return "[无标题]"
        return cleaned

    cleaned = []
    prev_level = 0

    for i, entry in enumerate(toc):
        if len(entry) < 3:
            continue

        try:
            level = int(entry[0])
            title = clean_title(entry[1])   # ←←← 关键修改：清洗标题
            page = int(entry[2])
        except (ValueError, TypeError):
            logger.warning(f"⚠️ 跳过无效书签条目 #{i}: {entry}")
            continue

        if level < 1:
            level = 1

        if i == 0:
            level = 1
            prev_level = 1
        else:
            if level > prev_level + 1:
                level = prev_level + 1
            prev_level = level

        cleaned.append([level, title, page] + entry[3:])

    if not cleaned:
        return []

    cleaned[0][0] = 1
    return cleaned


def _run_ghostscript(
    input_path: Path,
    output_path: Path,
    gs_args: list[str],
    operation_name: str = "operation",
):
    """通用 Ghostscript 执行器"""
    logger.info(f"⚙️ [{operation_name}] 使用 Ghostscript 处理 PDF: {input_path} → {output_path}")

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
                logger.info(f"📦 [{operation_name}] 使用本地 Ghostscript: {gs_path}")
            else:
                raise RuntimeError(
                    "未找到 Ghostscript。请确保 gswin64c.exe 在系统 PATH 中，"
                    "或将其放在项目目录的 gs10.06.0/bin/ 下。"
                )
    else:
        gs_path = "gs"

    cmd = [
        gs_path,
        "-q",
        "-dNOPAUSE",
        "-dBATCH",
        "-sDEVICE=pdfwrite",
        f"-sOutputFile={output_path}",
        str(input_path),
    ] + gs_args

    logger.debug(f"🔧 [{operation_name}] 执行命令: {' '.join(cmd)}")

    try:
        start_time = time.time()
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        duration = time.time() - start_time

        if result.returncode != 0:
            logger.error(f"❌ Ghostscript {operation_name} 失败:\n{result.stderr}")
            raise RuntimeError(f"Ghostscript {operation_name} 失败: {result.stderr.strip()}")
        else:
            orig_size = input_path.stat().st_size
            new_size = output_path.stat().st_size
            ratio = (1 - new_size / orig_size) * 100 if orig_size > 0 else 0
            logger.info(
                f"✅ [{operation_name}] 完成，耗时 {duration:.2f}s，体积减少 {ratio:.1f}% "
                f"({orig_size/1e6:.2f}MB → {new_size/1e6:.2f}MB)"
            )
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"Ghostscript {operation_name} 超时（>600秒）")
    except Exception as e:
        raise RuntimeError(f"调用 Ghostscript 执行 {operation_name} 时出错: {e}")


def rotate_pages_to_upright(input_path: Path, output_path: Path):
    """标准化：旋转页面为正向，保留字体和图像质量"""
    args = [
        "-dPDFSETTINGS=/default",
        "-dEmbedAllFonts=true",
        "-dSubsetFonts=true",
        "-dPassThroughJPEGImages=true",
        "-dDownsampleColorImages=false",
        "-dDownsampleGrayImages=false",
        "-dDownsampleMonoImages=false",
        "-dAutoRotatePages=/PageByPage",
        "-dUseCropBox=true",
    ]
    _run_ghostscript(input_path, output_path, args, operation_name="standardize")


def physically_unrotate_pages(input_path: Path, output_path: Path):
    """
    使用 PyMuPDF 物理消除页面的 /Rotate 属性：
    - 对于 rotation != 0 的页面，将其内容真正旋转到 upright 状态；
    - 设置 rotation = 0；
    - 自动调整 annotations/links/widgets 的位置。
    """
    logger.info(f"🔄 [unrotate] 物理消除页面旋转: {input_path} → {output_path}")
    try:
        doc = fitz.open(str(input_path))
        modified = False
        for page in doc:
            if page.rotation != 0:
                page.remove_rotation()
                modified = True
        if modified:
            logger.debug("📄 检测到旋转页面，已物理校正")
        else:
            logger.debug("📄 无旋转页面，跳过处理")
        doc.save(str(output_path), garbage=4, deflate=True, deflate_images=False, clean=True)
        doc.close()
        logger.info(f"✅ [unrotate] 完成: {output_path.name}")
    except Exception as e:
        logger.error(f"❌ [unrotate] 处理失败: {e}")
        raise RuntimeError(f"物理去旋转失败: {e}")


def _create_chunk_with_toc(
    src_doc: fitz.Document,
    start_page: int,
    end_page: int,
    output_path: Path,
    full_toc: Optional[List[List]],
):
    """用 fitz 分割并注入局部书签，生成中间文件（带书签）"""
    new_doc = fitz.open()
    new_doc.insert_pdf(src_doc, from_page=start_page, to_page=end_page)

    if full_toc:
        filtered_toc = []
        for entry in full_toc:
            if len(entry) < 3:
                continue
            level, title, global_page_1based = entry[0], entry[1], entry[2]
            global_page_0based = global_page_1based - 1  # fitz TOC 是 1-based
            if start_page <= global_page_0based <= end_page:
                rel_page_0based = global_page_0based - start_page
                rel_page_1based = rel_page_0based + 1
                new_entry = [level, title, rel_page_1based] + entry[3:]
                filtered_toc.append(new_entry)
        
        if filtered_toc:
            filtered_toc = sanitize_toc(filtered_toc)
            if filtered_toc:
                new_doc.set_toc(filtered_toc)

    new_doc.save(str(output_path))
    new_doc.close()


def _standardize_single_chunk(args: Tuple[Path, Path]) -> Path:
    """
    四步核心逻辑：
    1. 从带书签的中间 chunk 提取 TOC；
    2. 用 GS 标准化得到无书签的干净 PDF（可能含 /Rotate）；
    3. 用 PyMuPDF 物理消除 /Rotate，生成真正 upright 的 PDF；
    4. 将 TOC 注入最终 PDF；
    5. 删除中间文件。
    """
    toc_chunk, final_std_chunk = args

    # Step 1: 提取并清洗书签
    toc = None
    try:
        doc = fitz.open(str(toc_chunk))
        raw_toc = doc.get_toc()
        doc.close()
        if raw_toc:
            toc = sanitize_toc(raw_toc)
    except Exception as e:
        logger.warning(f"⚠️ 无法从 {toc_chunk.name} 提取或清洗书签: {e}")

    # Step 2: Ghostscript 标准化（会丢弃书签，但可能保留 /Rotate）
    gs_temp_path = toc_chunk.with_suffix(".gs_temp.pdf")
    rotate_pages_to_upright(toc_chunk, gs_temp_path)

    # Step 3: 物理消除旋转（关键步骤！）
    physically_unrotate_pages(gs_temp_path, final_std_chunk)
    gs_temp_path.unlink(missing_ok=True)  # 清理临时 GS 输出

    # Step 4: 重新注入书签
    if toc:
        try:
            out_doc = fitz.open(str(final_std_chunk))
            max_page = len(out_doc)
            # 检查是否有书签页码越界
            invalid = any(entry[2] > max_page for entry in toc)
            if invalid:
                logger.warning(f"⚠️ 书签页码超出范围（共 {max_page} 页），跳过注入: {final_std_chunk.name}")
            else:
                out_doc.set_toc(toc)
                out_doc.saveIncr()
                logger.debug(f"🔁 成功为 {final_std_chunk.name} 恢复 {len(toc)} 条书签")
            out_doc.close()
        except Exception as e:
            logger.warning(f"⚠️ 书签注入失败: {e}")

    # Step 5: 删除中间带书签文件
    try:
        toc_chunk.unlink()
        logger.info(f"🗑️ 已删除中间文件: {toc_chunk.name}")
    except Exception as e:
        logger.warning(f"⚠️ 删除中间文件失败: {toc_chunk} - {e}")

    return final_std_chunk


def preprocess_and_split_pdf(
    input_pdf: Path,
    workdir: Path,
    chunk_size: int,
    base_stem: str = "preprocessed",
    max_workers: int = None,
) -> List[Path]:
    """
    主函数：分割大 PDF，每个 chunk 都保留其对应书签。
    返回最终标准化后的 chunk 列表（简洁命名，无中间文件）。
    """
    chunks_dir = workdir / "chunks"
    chunks_dir.mkdir(exist_ok=True)
    logger.info(f"📁 创建 chunks 目录: {chunks_dir}")

    # === 第一步：打开原始 PDF 并提取完整书签 ===
    try:
        src_doc = fitz.open(str(input_pdf))
    except Exception as e:
        logger.error(f"❌ 无法打开原始 PDF: {e}")
        raise

    total_pages = len(src_doc)
    logger.info(f"📊 原始文档共 {total_pages} 页")

    full_toc = src_doc.get_toc()
    if full_toc:
        logger.info(f"🔖 检测到 {len(full_toc)} 条书签")
        # ===== 调试信息 =====
        logger.info(f"🔍 第一条书签: {full_toc[0]}")
        invalid_levels = [i for i, e in enumerate(full_toc) if e[0] < 1]
        if invalid_levels:
            logger.warning(f"⚠️ 发现 {len(invalid_levels)} 条 level < 1 的书签，例如索引 {invalid_levels[:5]}")
        # ===================

        # 清洗原始 TOC（可选，但推荐）
        full_toc = sanitize_toc(full_toc)
        if not full_toc:
            logger.warning("🧹 清洗后无有效书签，后续将不注入书签")
    else:
        logger.info("ℹ️ 原始 PDF 无书签")

    # === 第二步：生成带书签的中间 chunk ===
    toc_chunk_paths = []
    for i in range(0, total_pages, chunk_size):
        start = i
        end = min(i + chunk_size, total_pages) - 1
        part_index = (i // chunk_size) + 1
        toc_chunk_file = chunks_dir / f"{base_stem}_raw_part_{part_index:03d}_with_toc.pdf"

        if not toc_chunk_file.exists():
            _create_chunk_with_toc(src_doc, start, end, toc_chunk_file, full_toc)
            page_range_str = f"页 {start + 1}–{end + 1}"
            logger.info(f"✂️ 创建带书签 chunk: {toc_chunk_file.name} ({page_range_str})")

        toc_chunk_paths.append(toc_chunk_file)

    src_doc.close()

    # === 第三步：定义最终输出路径（简洁命名）===
    final_std_paths = [
        chunks_dir / f"{base_stem}_part_{(i // chunk_size) + 1:03d}.pdf"
        for i in range(0, total_pages, chunk_size)
    ]

    # 构建任务：(中间带书签文件, 最终标准文件)
    tasks = [
        (toc_chunk, final_std)
        for toc_chunk, final_std in zip(toc_chunk_paths, final_std_paths)
        if not final_std.exists()
    ]

    skipped = len(toc_chunk_paths) - len(tasks)
    if skipped:
        logger.info(f"⏭️ {skipped} 个 chunk 已存在，跳过处理")

    # === 第四步：并发处理 ===
    if tasks:
        logger.info(f"🚀 启动并发标准化与书签恢复，共 {len(tasks)} 个任务")
        failed_tasks = []
        with concurrent.futures.ProcessPoolExecutor(max_workers=max_workers) as executor:
            future_to_task = {
                executor.submit(_standardize_single_chunk, task): task
                for task in tasks
            }

            for future in concurrent.futures.as_completed(future_to_task):
                toc_chunk, final_std = future_to_task[future]
                try:
                    result_path = future.result()
                    logger.info(f"✅ 完成: {result_path.name}")
                except Exception as exc:
                    logger.error(f"💥 任务失败: {final_std.name} - {exc}")
                    failed_tasks.append((toc_chunk, final_std, exc))

        if failed_tasks:
            raise RuntimeError(f"标准化阶段有 {len(failed_tasks)} 个任务失败，请查看日志。")

    logger.info("✅ PDF 分割、标准化、书签保留及清理全部完成")
    return final_std_paths