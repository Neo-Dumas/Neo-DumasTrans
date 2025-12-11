# core/mineru_api.py

import requests
import time
import logging
from pathlib import Path
from typing import Dict
import zipfile
from io import BytesIO

logger = logging.getLogger(__name__)


def _download_and_extract_middle_json(zip_url: str, headers: dict, output_dir: str, stem: str, mode: str = "vlm") -> str | None:
    """
    下载 MinerU 返回的 ZIP 包：
      1. 保存到本地
      2. 解压全部内容
      3. 将其中的 layout.json 重命名为 {stem}_middle.json 并保存
      4. 返回该文件路径（保持与旧逻辑兼容）
    """
    try:
        # === Step 1: 创建本地目录 ===
        target_dir = Path(output_dir) / stem / mode
        target_dir.mkdir(parents=True, exist_ok=True)

        # === Step 2: 定义路径 ===
        zip_path = target_dir / f"{stem}.zip"
        middle_json_path = target_dir / f"{stem}_middle.json"  # 兼容旧名

        # === Step 3: 下载 ZIP ===
        logger.info(f"📥 Downloading ZIP to disk: {zip_path}")
        with requests.get(zip_url, headers=headers, timeout=60, stream=True) as r:
            r.raise_for_status()
            with open(zip_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
        logger.info(f"✅ ZIP saved to {zip_path}")

        # === Step 4: 解压 ZIP ===
        logger.info(f"📦 Extracting all files from {zip_path} to {target_dir}...")
        with zipfile.ZipFile(zip_path, 'r') as z:
            z.extractall(target_dir)
        logger.info(f"✅ ZIP extracted successfully")

        # === Step 5: 查找 layout.json ===
        layout_json_path = None
        for file_path in target_dir.rglob("layout.json"):
            layout_json_path = file_path
            break  # 取第一个

        if not layout_json_path:
            logger.error("❌ layout.json not found in extracted files")
            return None

        # === Step 6: 复制并重命名为 {stem}_middle.json ===
        import shutil
        shutil.copy(layout_json_path, middle_json_path)
        logger.info(f"🔄 Renamed {layout_json_path.name} -> {middle_json_path.name}")

        return str(middle_json_path)  # 返回兼容路径

    except Exception as e:
        logger.error(f"❌ Failed to download or process ZIP: {e}")
        return None

def run_mineru_api(pdf_path: str, output_dir: str, api_key: str, base_url: str = "https://mineru.net/api/v4") -> Dict:
    """
    调用 MinerU API 提取 PDF，并自动将 layout.json 保存到本地指定目录
    然后将其改名为_middle.json,与本地版保持一致：输出文件路径为 {output_dir}/{stem}/vlm/{stem}_middle.json
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        return {
            "success": False,
            "error": f"PDF file not found: {pdf_path}",
            "output_path": ""
        }

    stem = pdf_path.stem
    mode = "vlm"  # API 使用 VLM 模式
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    try:
        # === Step 1: 申请上传链接 ===
        apply_url = f"{base_url.rstrip('/')}/file-urls/batch"
        logger.info(f"📎 Applying for upload URL for {stem}.pdf...")

        payload = {
            "model_version": "vlm",
            "files": [
                {
                    "name": pdf_path.name,
                    "data_id": f"{stem}_{int(time.time())}"
                }
            ]
        }

        apply_res = requests.post(apply_url, headers=headers, json=payload, timeout=30)
        if apply_res.status_code != 200:
            return {
                "success": False,
                "error": f"Failed to apply upload URL [{apply_res.status_code}]: {apply_res.text[:200]}",
                "output_path": ""
            }

        apply_data = apply_res.json()
        if apply_data.get("code") != 0:
            return {
                "success": False,
                "error": f"Apply upload URL failed: {apply_data.get('msg', 'Unknown error')}",
                "output_path": ""
            }

        batch_id = apply_data["data"]["batch_id"]
        upload_url = apply_data["data"]["file_urls"][0]
        logger.info(f"✅ Upload URL obtained. Batch ID: {batch_id}")

        # === Step 2: 上传本地文件 ===
        logger.info("📤 Uploading local file...")
        with open(pdf_path, 'rb') as f:
            upload_headers = {}  # 上传时不要设置 Content-Type
            upload_res = requests.put(upload_url, data=f, headers=upload_headers, timeout=60)

        if upload_res.status_code != 200:
            return {
                "success": False,
                "error": f"File upload failed [{upload_res.status_code}]: {upload_res.text[:200]}",
                "output_path": ""
            }

        logger.info("✅ File uploaded successfully. MinerU is processing...")

        # === Step 3: 轮询任务状态 ===
        poll_url = f"{base_url.rstrip('/')}/extract-results/batch/{batch_id}"
        max_attempts = 60
        polling_interval = 10

        for attempt in range(max_attempts):
            time.sleep(polling_interval)
            logger.debug(f"🔁 Polling extraction result... (Attempt {attempt + 1}/{max_attempts})")

            try:
                poll_res = requests.get(poll_url, headers=headers, timeout=10)
                if poll_res.status_code != 200:
                    continue

                poll_data = poll_res.json()
                if poll_data.get("code") != 0:
                    logger.warning(f"Polling failed: {poll_data.get('msg')}")
                    continue

                results = poll_data["data"].get("extract_result", [])
                if not results:
                    continue

                first_result = results[0]
                state = first_result["state"]

                if state == "done":
                    zip_url = first_result.get("full_zip_url")
                    if not zip_url:
                        return {
                            "success": False,
                            "error": "Extraction succeeded but no full_zip_url returned",
                            "output_path": ""
                        }

                    # ✅ 关键：自动下载并提取 middle.json
                    local_output_path = _download_and_extract_middle_json(
                        zip_url=zip_url,
                        headers=headers,
                        output_dir=output_dir,
                        stem=stem,
                        mode=mode
                    )

                    if local_output_path:
                        logger.info(f"🎉 API processing completed. Result saved at: {local_output_path}")
                        return {
                            "success": True,
                            "error": "",
                            "output_path": local_output_path
                        }
                    else:
                        return {
                            "success": False,
                            "error": "Extraction succeeded but failed to download or extract middle.json",
                            "output_path": ""
                        }

                elif state == "failed":
                    err_msg = first_result.get("err_msg", "Unknown error")
                    logger.error(f"❌ Extraction failed: {err_msg}")
                    return {
                        "success": False,
                        "error": f"Extraction failed: {err_msg}",
                        "output_path": ""
                    }

                elif state == "running":
                    progress = first_result.get("extract_progress", {})
                    done = progress.get("extracted_pages", 0)
                    total = progress.get("total_pages", 1)
                    logger.info(f"📊 Progress: {done}/{total} pages processed...")

            except Exception as e:
                logger.warning(f"⚠️ Error during polling: {e}")

        return {
            "success": False,
            "error": "Extraction polling timed out after 10 minutes",
            "output_path": ""
        }

    except requests.exceptions.Timeout as e:
        return {
            "success": False,
            "error": f"Request timed out: {str(e)}",
            "output_path": ""
        }
    except requests.exceptions.ConnectionError as e:
        return {
            "success": False,
            "error": f"Network connection failed: {str(e)}",
            "output_path": ""
        }
    except Exception as e:
        logger.exception(f"❌ Unexpected error in run_mineru_api: {e}")
        return {
            "success": False,
            "error": f"Unexpected error: {str(e)}",
            "output_path": ""
        }