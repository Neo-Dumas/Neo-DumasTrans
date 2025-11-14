# core/mineru_local.py

import os
import subprocess
import logging
from pathlib import Path

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


def _find_mineru_cmd():
    possible_cmds = [
        ["mineru"],
        ["python", "-m", "mineru.main"],
    ]
    for cmd in possible_cmds:
        try:
            subprocess.run(cmd + ["--help"], capture_output=True, text=True, timeout=10, check=True)
            return cmd
        except Exception:
            continue
    raise RuntimeError("Local mineru command not found. Please install MinerU.")


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


def _run_mineru_local_to_dir(pdf_path: str, output_dir: str) -> bool:
    """Run local MinerU (txt mode)"""
    try:
        mineru_cmd = _find_mineru_cmd()
        cmd = mineru_cmd + [
            "-p", os.path.abspath(pdf_path),
            "-o", output_dir,
            "-m", "txt", 
        ]
        logger.info(f"🔁 Running local MinerU (txt) on {Path(pdf_path).name}")
        result = subprocess.run(cmd, text=True, timeout=600)
        return result.returncode == 0
    except Exception as e:
        logger.warning(f"Local MinerU (txt) failed: {e}")
        return False


def _run_mineru_local_ocr_to_dir(pdf_path: str, output_dir: str) -> bool:
    """Run local MinerU in ocr mode (default method)"""
    try:
        mineru_cmd = _find_mineru_cmd()
        cmd = mineru_cmd + [
            "-p", os.path.abspath(pdf_path),
            "-o", output_dir,
            "-m", "ocr",
        ]
        logger.info(f"🔁 Running local MinerU (ocr) on {Path(pdf_path).name}")
        result = subprocess.run(cmd, text=True, timeout=600)
        return result.returncode == 0
    except Exception as e:
        logger.warning(f"Local MinerU (ocr) failed: {e}")
        return False


def detect_mode() -> str:
    """Detect available mode: 'vlm' if WSL available, else 'txt'"""
    return "vlm" if _is_wsl_available() else "txt"


def run_local(pdf_path: str, output_dir: str, mode: str) -> bool:
    """Run local MinerU in specified mode: 'vlm', 'txt', or 'ocr'"""
    if mode == "vlm":
        return _run_mineru_in_wsl_to_dir(pdf_path, output_dir)
    elif mode == "txt":
        return _run_mineru_local_to_dir(pdf_path, output_dir)
    elif mode == "ocr":
        return _run_mineru_local_ocr_to_dir(pdf_path, output_dir)
    else:
        logger.error(f"Unsupported local mode: {mode}")
        return False