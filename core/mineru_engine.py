# core/mineru_engine.py
import os
from pathlib import Path
import logging

from .mineru_local import run_local
from .mineru_api import run_mineru_api

# ======================
# 配置区
# ======================
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MINERU_OUTPUT_DIR = os.path.join(PROJECT_ROOT, ".mineru_output")

logger = logging.getLogger(__name__)


def _is_successfully_processed(stem: str, output_dir: str, mode: str) -> bool:
    """检查是否已成功生成中间 JSON 文件"""
    middle_json_path = Path(output_dir) / stem / mode / f"{stem}_middle.json"
    return middle_json_path.exists() and middle_json_path.stat().st_size > 0


def _build_success_result(stem: str, output_dir: str, mode: str) -> dict:
    """构建成功结果字典"""
    middle_json_path = Path(output_dir) / stem / mode / f"{stem}_middle.json"
    logger.debug(f"✅ 构建成功结果，目标中间文件路径: {middle_json_path}")
    return {
        "success": True,
        "error": "",
        "output_path": str(middle_json_path)
    }


def _run_local_with_retry(pdf_path: str, output_dir: str, pdf_type: str, stem: str) -> dict:
    """本地处理，最多重试 2 次"""
    for attempt in range(2):
        logger.info(f"📦 Local processing attempt {attempt + 1} for {stem} in {pdf_type} mode...")
        if run_local(pdf_path, output_dir, pdf_type):
            return _build_success_result(stem, output_dir, pdf_type)
        logger.warning(f"📦 Local attempt {attempt + 1} failed for {stem}")
    
    return {
        "success": False,
        "error": f"MinerU local processing failed after 2 attempts for {stem}",
        "output_path": ""
    }


def _run_api_with_fallback(
    pdf_path: str,
    output_dir: str,
    stem: str,
    mineru_api_key: str,
    mineru_base_url: str
) -> dict:
    """先尝试 API（2 次），失败后 fallback 到本地（2 次）"""
    base_url = mineru_base_url or "https://api.mineru.ai"

    # === 尝试 API ===
    for attempt in range(2):
        logger.info(f"☁️  API attempt {attempt + 1} for {stem}...")
        result = run_mineru_api(
            pdf_path=pdf_path,
            output_dir=output_dir,
            api_key=mineru_api_key,
            base_url=base_url
        )
        if result["success"]:
            logger.info(f"✅ Successfully processed {stem} via API")
            return result
        logger.warning(f"☁️  API attempt {attempt + 1} failed: {result['error']}")

    logger.warning(f"☁️  API failed after 2 attempts for {stem}. Falling back to local...")

    # === Fallback 到本地 ===
    return _run_local_with_retry(pdf_path, output_dir, "vlm", stem)


def run_single_pdf(
    pdf_path: str,
    output_dir: str,
    pdf_type: str = None,
    mineru_api_key: str = None,
    mineru_base_url: str = None,
) -> dict:
    """
    处理单个 PDF 文件，根据类型选择处理方式：
      - txt/ocr: 仅本地处理（带重试）
      - vlm: 先 API（带重试），失败后 fallback 到本地（也带重试）
    若已成功处理过，则直接跳过。
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


    # 跳过已成功处理的文件
    if _is_successfully_processed(stem, output_dir, pdf_type):
        logger.info(f"⏭️  Skipping {stem} (already processed)")
        return _build_success_result(stem, output_dir, pdf_type)

    # 分支处理
    if pdf_type in ("txt", "ocr"):
        logger.info(f"📄 Detected {pdf_type} mode for {stem}, using local processing only.")
        return _run_local_with_retry(pdf_path, output_dir, pdf_type, stem)

    elif pdf_type == "vlm":
        if not mineru_api_key:
            logger.warning(f"⚠️  No API key provided for vlm mode; falling back to local for {stem}")
            return _run_local_with_retry(pdf_path, output_dir, "vlm", stem)
        return _run_api_with_fallback(pdf_path, output_dir, stem, mineru_api_key, mineru_base_url)

    else:
        return {
            "success": False,
            "error": f"Unsupported pdf_type: {pdf_type}",
            "output_path": ""
        }