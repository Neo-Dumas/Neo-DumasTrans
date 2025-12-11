# core/mineru_local.py
import logging
import requests
import time
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)


def _find_latest_uuid_subdir(parent: Path) -> Path:
    """找出 parent 下最新的、非空的子目录（MinerU API 生成的 UUID 目录）"""
    subdirs = [d for d in parent.iterdir() if d.is_dir()]
    if not subdirs:
        raise FileNotFoundError("未找到任何子目录")
    return max(subdirs, key=lambda d: d.stat().st_mtime)


def _run_via_local_api(
    pdf_path: str,
    output_dir: str,
    parse_method: str = None,
    backend: str = None,
    api_base_url: str = "http://127.0.0.1:8000"
) -> bool:
    """
    通过本地已启动的 MinerU API 服务处理 PDF。
    - 若 backend 指定（如 'vlm-lmdeploy-engine'），则优先使用 backend；
    - 否则 fallback 到 parse_method（用于 txt/ocr 兼容）。
    """
    pdf_path = Path(pdf_path)
    output_root = Path(output_dir)
    logger.info(f"📤 通过本地 API 处理: {pdf_path.name} (backend={backend or parse_method})")

    try:
        with open(pdf_path, 'rb') as f:
            files = {'files': (pdf_path.name, f, 'application/pdf')}
            data = {
                'output_dir': str(output_root),
                'lang_list': ['en'],
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

            # 设置解析后端
            if backend:
                data['backend'] = backend
            elif parse_method in ("txt", "ocr"):
                data['parse_method'] = parse_method
            else:
                logger.error("❌ 必须指定 backend 或有效的 parse_method（txt/ocr）")
                return False

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

        for content_parent in uuid_dir.iterdir():
            if not content_parent.is_dir():
                continue

            target_dir = output_root / content_parent.name
            target_dir.mkdir(parents=True, exist_ok=True)

            for item in content_parent.iterdir():
                dest_item = target_dir / item.name
                if item.is_dir():
                    if dest_item.exists():
                        logger.debug(f"🔄 合并目录: {item} -> {dest_item}")
                        shutil.copytree(item, dest_item, dirs_exist_ok=True)
                        shutil.rmtree(item)
                    else:
                        shutil.move(str(item), str(dest_item))
                else:
                    if dest_item.exists():
                        dest_item.unlink()
                    shutil.move(str(item), str(dest_item))

        logger.info(f"✅ 提取成功: {output_root}")
        shutil.rmtree(uuid_dir, ignore_errors=True)
        return True

    except Exception as e:
        logger.error(f"💥 本地 API 处理异常: {pdf_path.name} - {e}")
        return False


def run_local(
    pdf_path: str,
    output_dir: str,
    mode: str,
    mineru_api_key: str = None,     # noqa: ARG001
    mineru_base_url: str = None     # noqa: ARG001
) -> bool:
    """
    统一通过本地 API 处理所有模式：
      - 'vlm'   → backend='vlm-lmdeploy-engine'
      - 'txt'   → parse_method='txt'
      - 'ocr'   → parse_method='ocr'
    """
    base_url = mineru_base_url or "http://127.0.0.1:8000"

    if mode == "vlm":
        return _run_via_local_api(
            pdf_path=pdf_path,
            output_dir=output_dir,
            backend="vlm-lmdeploy-engine",
            api_base_url=base_url
        )
    elif mode in ("txt", "ocr"):
        return _run_via_local_api(
            pdf_path=pdf_path,
            output_dir=output_dir,
            parse_method=mode,
            api_base_url=base_url
        )
    else:
        logger.error(f"❌ 不支持的本地模式: {mode}")
        return False