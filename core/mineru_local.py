# core/mineru_local.py
import os
import subprocess
import logging
import requests
import time
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)


# ==========================
# WSL 相关工具函数
# ==========================

def _is_wsl_available() -> bool:
    """检测系统是否支持 WSL"""
    try:
        result = subprocess.run(["wsl", "echo", "test"], capture_output=True, text=True, timeout=10)
        return result.returncode == 0
    except Exception as e:
        logger.debug(f"WSL 检测失败: {e}")
        return False


def _windows_to_wsl_path(win_path: str) -> str:
    """将 Windows 路径转换为 WSL 路径"""
    win_path = os.path.abspath(win_path)
    if win_path.startswith("\\\\"):
        raise ValueError("UNC paths not supported in WSL")
    drive, tail = os.path.splitdrive(win_path)
    drive = drive.rstrip(":").lower()
    return f"/mnt/{drive}{tail.replace(os.sep, '/')}"


def _run_vlm_in_wsl(pdf_path: str, output_dir: str) -> bool:
    """在 WSL 中运行 MinerU VLM 模式"""
    if not _is_wsl_available():
        logger.warning("WSL 不可用，无法运行 VLM 模式")
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
        logger.info(f"🚀 在 WSL 中运行 MinerU (VLM): {Path(pdf_path).name}")
        result = subprocess.run(cmd, timeout=600)
        success = result.returncode == 0
        if not success:
            logger.warning(f"WSL MinerU (VLM) 返回非零状态码: {result.returncode}")
        return success
    except Exception as e:
        logger.error(f"WSL MinerU (VLM) 执行异常: {e}")
        return False


# ==========================
# 本地 HTTP API 相关函数
# ==========================

def _find_latest_uuid_subdir(parent: Path) -> Path:
    """找出 parent 下最新的、非空的子目录（MinerU API 生成的 UUID 目录）"""
    subdirs = [d for d in parent.iterdir() if d.is_dir()]
    if not subdirs:
        raise FileNotFoundError("未找到任何子目录")
    return max(subdirs, key=lambda d: d.stat().st_mtime)


def _run_txt_or_ocr_via_local_api(
    pdf_path: str,
    output_dir: str,
    parse_method: str,
    api_base_url: str = "http://127.0.0.1:8000"
) -> bool:
    """
    通过本地已启动的 MinerU API 服务处理 PDF（仅支持 txt / ocr 模式）
    """
    if parse_method not in ("txt", "ocr"):
        logger.error(f"❌ 本地 API 仅支持 'txt' 或 'ocr' 模式，收到: {parse_method}")
        return False

    pdf_path = Path(pdf_path)
    output_root = Path(output_dir)
    target_final_dir = output_root / pdf_path.stem
    logger.info(f"📤 通过本地 API 处理: {pdf_path.name} (parse_method={parse_method})")

    try:
        with open(pdf_path, 'rb') as f:
            files = {'files': (pdf_path.name, f, 'application/pdf')}
            data = {
                'output_dir': str(output_root),
                'lang_list': ['en'],
                'parse_method': parse_method,
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
            logger.error(f"❌ 本地 API 返回错误 ({response.status_code}): {pdf_path.name}")
            return False

        time.sleep(2)

        # 定位并移动结果目录
        uuid_dir = _find_latest_uuid_subdir(output_root)
        logger.debug(f"📁 找到临时 UUID 目录: {uuid_dir.name}")

        # 遍历 UUID 目录下的所有子目录（通常只有一个：<pdf_stem>）
        for content_parent in uuid_dir.iterdir():
            if not content_parent.is_dir():
                continue

            target_dir = output_root / content_parent.name  # e.g., output_root/俄文第一页_part_001
            target_dir.mkdir(parents=True, exist_ok=True)

            # 将 content_parent 下的所有子项（txt/, ocr/, images/ 等）合并到 target_dir
            for item in content_parent.iterdir():
                dest_item = target_dir / item.name
                if item.is_dir():
                    if dest_item.exists():
                        # 已存在同名目录 → 递归合并（这里简化为：先删后移，或更安全地 shutil.copytree + dirs_exist_ok）
                        logger.debug(f"🔄 合并目录: {item} -> {dest_item}")
                        # Python 3.8+ 支持 dirs_exist_ok
                        shutil.copytree(item, dest_item, dirs_exist_ok=True)
                        shutil.rmtree(item)  # 清理源
                    else:
                        shutil.move(str(item), str(dest_item))
                else:
                    # 处理文件（如有）
                    if dest_item.exists():
                        dest_item.unlink()
                    shutil.move(str(item), str(dest_item))

        logger.info(f"✅ 提取成功: {output_root}")

        # 清理临时 UUID 目录（此时应为空或可安全删除）
        shutil.rmtree(uuid_dir, ignore_errors=True)
        return True

    except Exception as e:
        logger.error(f"💥 本地 API 处理异常: {pdf_path.name} - {e}")
        return False


# ==========================
# 公共接口
# ==========================

def run_local(
    pdf_path: str,
    output_dir: str,
    mode: str,
    # 注意：以下两个参数保留以兼容调用方，但本地模式不使用它们
    mineru_api_key: str = None,     # noqa: ARG001
    mineru_base_url: str = None     # noqa: ARG001
) -> bool:
    """
    根据指定模式运行本地 MinerU：
      - 'vlm': 通过 WSL 命令行调用（GPU VLM）
      - 'txt' / 'ocr': 通过本地已启动的 HTTP API 服务处理
    """
    if mode == "vlm":
        return _run_vlm_in_wsl(pdf_path, output_dir)
    elif mode in ("txt", "ocr"):
        base_url = mineru_base_url or "http://127.0.0.1:8000"
        return _run_txt_or_ocr_via_local_api(pdf_path, output_dir, mode, base_url)
    else:
        logger.error(f"❌ 不支持的本地模式: {mode}")
        return False