# core/mineru_local.py

import os
import subprocess
import logging
import requests
import time
import shutil
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def _is_wsl_available():
    try:
        result = subprocess.run(["wsl", "echo", "test"], capture_output=True, text=True, timeout=10)
        return result.returncode == 0
    except Exception:
        return False


def _windows_to_wsl_path(win_path: str) -> str:
    win_path = os.path.abspath(win_path)
    if win_path.startswith("\\\\"):
        raise ValueError("UNC paths not supported in WSL")
    drive, tail = os.path.splitdrive(win_path)
    drive = drive.rstrip(":").lower()
    return f"/mnt/{drive}{tail.replace(os.sep, '/')}"


def _run_mineru_in_wsl_to_dir(pdf_path: str, output_dir: str) -> bool:
    """Run MinerU in WSL (VLM mode)"""
    if not _is_wsl_available():
        return False
    try:
        wsl_pdf = _windows_to_wsl_path(pdf_path)
        wsl_out = _windows_to_wsl_path(output_dir)
        subprocess.run(["wsl", "mkdir", "-p", wsl_out], check=True, timeout=10)

        cmd = [
            "wsl",
            "env",
            "HF_ENDPOINT=https://hf-mirror.com",
            "HF_HOME=/home/xin/.cache/huggingface",
            "/home/xin/miniconda3/envs/pdf-llm/bin/mineru",
            "-p", wsl_pdf,
            "-o", wsl_out,
            "-b", "vlm-vllm-engine",
            "-f", "true",
            "-t", "true",
            "--device", "cuda"
        ]
        logger.info(f"🚀 Running WSL MinerU (VLM) on {Path(pdf_path).name}")
        result = subprocess.run(cmd, timeout=600)
        return result.returncode == 0
    except Exception as e:
        logger.warning(f"WSL MinerU (VLM) failed: {e}")
        return False


def _find_latest_uuid_subdir(parent: Path) -> Path:
    """找出 parent 下最新的、非空的子目录（即 MinerU 生成的 UUID 目录）"""
    subdirs = [d for d in parent.iterdir() if d.is_dir()]
    if not subdirs:
        raise FileNotFoundError("未找到任何子目录")
    latest = max(subdirs, key=lambda d: d.stat().st_mtime)
    return latest


def run_mineru_via_api(
    pdf_path: str,
    output_dir: str,
    mode: str,
    api_base_url: str = "http://127.0.0.1:8000"
) -> bool:
    """
    使用已启动的 MinerU API 处理 PDF。
    mode 必须是 'txt' 或 'ocr'，将直接作为 parse_method 传给 API。
    """
    if mode not in ("txt", "ocr"):
        logger.error(f"❌ 不支持的 API 模式: {mode}，仅支持 'txt' 或 'ocr'")
        return False

    pdf_path = Path(pdf_path)
    output_root = Path(output_dir)
    target_final_dir = output_root / pdf_path.stem

    # 断点续传：如果最终目标已存在，跳过
    if target_final_dir.exists():
        logger.info(f"⏭️ 已存在，跳过: {pdf_path.stem}")
        return True

    logger.info(f"📤 正在通过 API 处理: {pdf_path.name} (parse_method={mode})")

    try:
        with open(pdf_path, 'rb') as f:
            files = {'files': (pdf_path.name, f, 'application/pdf')}
            data = {
                'output_dir': str(output_root),
                'lang_list': ['en'],
                'parse_method': mode,  # ✅ 根据 mode 决定 parse_method
                'formula_enable': True,
                'table_enable': True,
                'return_md': True,
                'return_middle_json': True,
                'return_model_output': True,
                'return_content_list': True,
                'return_images': True,
                'response_format_zip': False,
                'start_page_id': 0,
                'end_page_id': -1
            }
            response = requests.post(
                f"{api_base_url}/file_parse",
                files=files,
                data=data,
                timeout=600
            )

        if response.status_code != 200:
            logger.error(f"❌ API 返回错误 ({response.status_code}): {pdf_path.name}")
            return False

        time.sleep(2)

        # 找到刚生成的 UUID 目录
        uuid_dir = _find_latest_uuid_subdir(output_root)
        logger.debug(f"📁 找到 UUID 目录: {uuid_dir.name}")

        # 进入 UUID 目录，找内容子目录
        expected_content_dir = uuid_dir / pdf_path.stem
        if not expected_content_dir.exists():
            candidates = [d for d in uuid_dir.iterdir() if d.is_dir() and d.name != uuid_dir.name]
            if not candidates:
                raise RuntimeError(f"未在 {uuid_dir} 中找到内容目录")
            expected_content_dir = candidates[0]

        # 移动到目标位置
        shutil.move(str(expected_content_dir), str(target_final_dir))
        logger.info(f"✅ 提取成功: {target_final_dir}")

        # 清理 UUID 目录
        shutil.rmtree(uuid_dir, ignore_errors=True)
        return True

    except Exception as e:
        logger.error(f"💥 API 处理异常: {pdf_path.name} - {e}")
        return False


def detect_mode() -> str:
    """Detect available mode: 'vlm' if WSL available, else 'txt'"""
    return "vlm" if _is_wsl_available() else "txt"


def run_local(
    pdf_path: str,
    output_dir: str,
    mode: str,
    mineru_api_key: Optional[str] = None,   # 保留参数签名以兼容调用方
    mineru_base_url: Optional[str] = None
) -> bool:
    """
    Run local MinerU in specified mode:
      - 'vlm': use WSL command line (GPU VLM engine, unchanged)
      - 'txt' or 'ocr': use already-running MinerU API via HTTP
    """
    base_url = mineru_base_url or "http://127.0.0.1:8000"

    if mode == "vlm":
        return _run_mineru_in_wsl_to_dir(pdf_path, output_dir)
    elif mode in ("txt", "ocr"):
        return run_mineru_via_api(pdf_path, output_dir, mode, api_base_url=base_url)
    else:
        logger.error(f"Unsupported local mode: {mode}")
        return False