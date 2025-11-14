# core/pdf_final_merger.py

"""
独立工具：使用 qpdf 合并 PDF 文件列表。
不保留书签、元数据等，追求最小体积。
【注意】本版本已移除自动压缩步骤。
"""

from pathlib import Path
import subprocess
from loguru import logger


def merge_all_final_pdfs(
    file_list: list,
    output_path: str = None,
    output_filename: str = "all_merged_output.pdf",
) -> dict:
    """
    使用 qpdf 合并 PDF 文件（不再进行压缩）。

    Args:
        file_list: PDF 文件路径列表（必需）
        output_path: 合并文件的完整输出路径（含文件名），优先级高于 output_filename
        output_filename: 若未指定 output_path，则使用此文件名

    Returns:
        {
            "success": bool,
            "output_path": str or None,
            "merged_count": int,
            "error": str or None
        }
    """
    if not file_list:
        error_msg = "文件列表为空，无可合并的 PDF 文件"
        logger.error(error_msg)
        return {"success": False, "output_path": None, "merged_count": 0, "error": error_msg}

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
        return {"success": False, "output_path": None, "merged_count": 0, "error": error_msg}

    # 排序确保顺序一致
    final_pdfs.sort(key=lambda p: p.name)
    logger.info(f"🔍 准备合并 {len(final_pdfs)} 个 PDF 文件")

    # 确定输出路径
    if output_path:
        final_output_path = Path(output_path).resolve()
    else:
        final_output_path = (final_pdfs[0].parent / output_filename).resolve()

    final_output_path.parent.mkdir(parents=True, exist_ok=True)

    # 如果目标文件存在，先删除（避免 qpdf 报错）
    if final_output_path.exists():
        try:
            final_output_path.unlink()
            logger.debug(f"🗑️ 已删除已存在的输出文件: {final_output_path}")
        except Exception as e:
            error_msg = f"无法删除已有文件 '{final_output_path}': {e}"
            logger.error(error_msg)
            return {"success": False, "output_path": None, "merged_count": 0, "error": error_msg}

    # === 使用 qpdf 合并 ===
    try:
        # 构建 qpdf 合并命令（正确格式：--pages 只出现一次）
        project_root = Path(__file__).parent.parent.resolve()
        qpdf_exe = project_root / "qpdf" / "qpdf-12.2.0-mingw64" / "bin" / "qpdf.exe"

        if not qpdf_exe.exists():
            error_msg = f"❌ qpdf 可执行文件未找到: {qpdf_exe}"
            logger.error(error_msg)
            return {"success": False, "output_path": None, "merged_count": 0, "error": error_msg}

        # 可选：打印 qpdf 版本用于调试（可注释掉）
        # version_check = subprocess.run([str(qpdf_exe), "--version"], capture_output=True, text=True)
        # logger.debug(f"qpdf version: {version_check.stdout.strip()}")

        # 正确构造命令：--empty --pages file1 1-z file2 1-z ... -- output.pdf
        cmd = [str(qpdf_exe), "--empty", "--pages"]
        for pdf in final_pdfs:
            cmd += [str(pdf), "1-z"]  # 每个 PDF + 全部页面
        cmd += ["--", str(final_output_path)]

        logger.info(f"🧩 正在使用 qpdf 合并 PDF → {final_output_path}")
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)

        if result.returncode != 0:
            error_msg = f"qpdf 合并失败: {result.stderr.strip()}"
            logger.error(f"❌ {error_msg}")
            return {"success": False, "output_path": None, "merged_count": 0, "error": error_msg}

        if not final_output_path.exists():
            error_msg = "qpdf 未生成输出文件"
            logger.error(f"❌ {error_msg}")
            return {"success": False, "output_path": None, "merged_count": 0, "error": error_msg}

        merged_count = len(final_pdfs)
        logger.success(f"🎉 合并完成！共 {merged_count} 个文件 → {final_output_path}")

        # ✅ 压缩步骤已完全移除

        return {
            "success": True,
            "output_path": str(final_output_path),
            "merged_count": merged_count,
            "error": None
        }

    except Exception as e:
        error_msg = f"合并过程中发生异常: {e}"
        logger.error(f"❌ {error_msg}", exc_info=True)
        return {"success": False, "output_path": None, "merged_count": 0, "error": error_msg}