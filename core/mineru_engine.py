# core/mineru_engine.py
import os
from pathlib import Path
import logging

from .mineru_local import run_local
from .mineru_api import run_mineru_api

logger = logging.getLogger(__name__)


def _build_success_result(stem: str, output_dir: str, mode: str) -> dict:
    middle_json_path = Path(output_dir) / stem / mode / f"{stem}_middle.json"
    return {
        "success": True,
        "error": "",
        "output_path": str(middle_json_path)
    }


def _run_local_with_retry(pdf_path: str, output_dir: str, mode: str, stem: str, max_retries: int = 2) -> dict:
    """仅本地处理，带重试"""
    for attempt in range(max_retries):
        logger.info(f"📦 Local attempt {attempt + 1}/{max_retries} for {stem} ({mode})")
        if run_local(pdf_path, output_dir, mode):
            return _build_success_result(stem, output_dir, mode)
        if attempt < max_retries - 1:
            logger.warning(f"📦 Local attempt {attempt + 1} failed, retrying...")
    return {
        "success": False,
        "error": f"Local processing failed after {max_retries} attempts",
        "output_path": ""
    }


def _run_remote_api_with_retry(
    pdf_path: str,
    output_dir: str,
    stem: str,
    api_key: str,
    base_url: str,
    max_retries: int = 2
) -> dict:
    """仅远程 API，带重试（无 fallback！）"""
    url = base_url or "https://api.mineru.ai"
    for attempt in range(max_retries):
        logger.info(f"☁️ Remote API attempt {attempt + 1}/{max_retries} for {stem}")
        result = run_mineru_api(
            pdf_path=pdf_path,
            output_dir=output_dir,
            api_key=api_key,
            base_url=url
        )
        if result["success"]:
            return result
        if attempt < max_retries - 1:
            logger.warning(f"☁️ API attempt {attempt + 1} failed: {result['error']}, retrying...")
    return result  # 返回最后一次失败结果


def run_single_pdf(
    pdf_path: str,
    output_dir: str,
    pdf_type: str,
    mineru_api_key: str = None,
    mineru_base_url: str = None,
) -> dict:
    """
    执行单个 PDF 处理，带重试，但 **无 fallback**：
      - txt/ocr：仅本地（重试）
      - vlm + 有 api_key：仅远程 API（重试）
      - vlm + 无 api_key：仅本地（重试）
    跳过逻辑和策略决策由调用方（mineru_processor）负责。
    """
    pdf_path = os.path.abspath(pdf_path)
    output_dir = os.path.abspath(output_dir)
    stem = Path(pdf_path).stem

    if not os.path.exists(pdf_path):
        return {
            "success": False,
            "error": f"PDF not found: {pdf_path}",
            "output_path": ""
        }

    if pdf_type not in ("txt", "ocr", "vlm"):
        return {
            "success": False,
            "error": f"Unsupported pdf_type: {pdf_type}",
            "output_path": ""
        }

    # ========== 核心：无 fallback，只有重试 ==========
    if pdf_type in ("txt", "ocr"):
        # 强制本地
        return _run_local_with_retry(pdf_path, output_dir, pdf_type, stem)

    elif pdf_type == "vlm":
        if mineru_api_key:
            # 强制远程（即使失败也不切本地）
            return _run_remote_api_with_retry(
                pdf_path, output_dir, stem,
                mineru_api_key, mineru_base_url
            )
        else:
            # 强制本地
            return _run_local_with_retry(pdf_path, output_dir, "vlm", stem)

    else:
        # 不可达
        return {
            "success": False,
            "error": "Unknown error in run_single_pdf",
            "output_path": ""
        }