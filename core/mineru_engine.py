# core/mineru_engine.py

import os
from pathlib import Path
import logging

from .mineru_local import detect_mode as detect_local_mode, run_local
from .mineru_api import run_mineru_api

# ======================
# 配置区
# ======================
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MINERU_OUTPUT_DIR = os.path.join(PROJECT_ROOT, ".mineru_output")

logger = logging.getLogger(__name__)


def _is_successfully_processed(stem: str, output_dir: str, mode: str) -> bool:
    middle_json_path = Path(output_dir) / stem / mode / f"{stem}_middle.json"
    return middle_json_path.exists() and middle_json_path.stat().st_size > 0


# ===================================
# ✅ 核心函数：只处理单个 PDF
# - txt/ocr: 直接本地处理（带一次重试）
# - vlm: 先 API（带一次重试），失败后 fallback 到本地（也带一次重试）
# ===================================
def run_single_pdf(
    pdf_path: str,
    output_dir: str,
    pdf_type: str = None,
    mineru_api_key: str = None,
    mineru_base_url: str = None,
) -> dict:
    pdf_path = os.path.abspath(pdf_path)
    output_dir = os.path.abspath(output_dir)
    stem = Path(pdf_path).stem

    if not os.path.exists(pdf_path):
        return {
            "success": False,
            "error": f"PDF not found: {pdf_path}",
            "output_path": ""
        }

    if pdf_type is None:
        pdf_type = detect_local_mode()

    # 检查是否已处理成功
    if _is_successfully_processed(stem, output_dir, pdf_type):
        logger.info(f"⏭️  Skipping {stem} (already processed)")
        middle_json_path = Path(output_dir) / stem / pdf_type / f"{stem}_middle.json"
        return {
            "success": True,
            "error": "",
            "output_path": str(middle_json_path)
        }

    def _run_local_with_retry():
        """本地模式：最多尝试 2 次"""
        for attempt in range(2):
            logger.info(f"📦 Local processing attempt {attempt + 1} for {stem} in {pdf_type} mode...")
            success = run_local(pdf_path, output_dir, pdf_type)
            if success:
                middle_json_path = Path(output_dir) / stem / pdf_type / f"{stem}_middle.json"
                return {
                    "success": True,
                    "error": "",
                    "output_path": str(middle_json_path)
                }
            else:
                logger.warning(f"📦 Local attempt {attempt + 1} failed for {stem}")
        return {
            "success": False,
            "error": f"MinerU local processing failed after 2 attempts for {stem}",
            "output_path": ""
        }

    # =============================
    # 📄 txt / ocr：直接走本地（带重试）
    # =============================
    if pdf_type in ("txt", "ocr"):
        logger.info(f"📄 Detected {pdf_type} mode for {stem}, using local processing only.")
        return _run_local_with_retry()

    # =============================
    # 🖼️ vlm：先尝试 API（带一次重试），失败再 fallback 到本地（也带重试）
    # =============================
    if pdf_type == "vlm":
        if mineru_api_key:
            base_url = mineru_base_url or "https://api.mineru.ai"
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
                else:
                    logger.warning(f"☁️  API attempt {attempt + 1} failed: {result['error']}")
            
            logger.warning(f"☁️  API failed after 2 attempts for {stem}. Falling back to local...")

        # fallback to local with retry
        return _run_local_with_retry()

    # 未知模式
    return {
        "success": False,
        "error": f"Unsupported pdf_type: {pdf_type}",
        "output_path": ""
    }