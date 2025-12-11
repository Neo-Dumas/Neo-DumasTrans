# utils/cleanup.py

import logging
import shutil
import time
from pathlib import Path
import os

logger = logging.getLogger(__name__)


def clear_workdir_if_too_large(max_age_days=7, max_size_gb=10):
    workdir = Path(os.getcwd()) / 'workdir'
    if not workdir.exists():
        logger.info("📁 workdir 不存在，跳过清理")
        return
    if not workdir.is_dir():
        logger.warning("⚠️ workdir 存在但不是目录，跳过清理")
        return

    logger.info(f"🧹 开始清理 workdir 中超过 {max_age_days} 天的文件...")

    # Step 1: 删除过期文件（按修改时间）
    cutoff_time = time.time() - max_age_days * 86400  # 86400 = 24*60*60 秒
    deleted_count = 0

    # 遍历所有文件和符号链接，删除过期项
    for item in workdir.rglob('*'):
        try:
            if item.is_file() or item.is_symlink():
                stat_result = item.stat()
                if stat_result.st_mtime < cutoff_time:
                    item.unlink()
                    deleted_count += 1
        except (OSError, FileNotFoundError) as e:
            logger.warning(f"⚠️ 无法处理文件 {item}: {e}")

    # 尝试删除空目录（从最深开始）
    all_items = sorted(workdir.rglob('*'), key=lambda x: len(str(x)), reverse=True)
    for item in all_items:
        try:
            if item.is_dir() and not any(item.iterdir()):
                item.rmdir()
        except (OSError, FileNotFoundError) as e:
            logger.warning(f"⚠️ 无法删除空目录 {item}: {e}")

    logger.info(f"🗑️ 已删除 {deleted_count} 个过期文件（> {max_age_days} 天）")

    # Step 2: 精确计算当前 workdir 总大小（含所有子目录）
    total_size = 0
    file_count = 0
    for item in workdir.rglob('*'):
        if item.is_file():
            try:
                st = item.stat()
                total_size += st.st_size
                file_count += 1
            except (OSError, FileNotFoundError) as e:
                logger.warning(f"⚠️ 无法获取文件大小 {item}: {e}")
                continue

    size_gb = total_size / (1024 ** 3)
    logger.info(f"📊 清理后 workdir 共 {file_count} 个文件，总大小: {size_gb:.3f} GB (阈值: {max_size_gb:.3f} GB)")

    # Step 3: 如果总大小仍超过阈值，彻底清空整个 workdir
    threshold_bytes = max_size_gb * (1024 ** 3)
    if total_size > threshold_bytes:
        logger.warning(
            f"⚠️ workdir 总大小 ({size_gb:.3f} GB) 超过阈值 ({max_size_gb:.3f} GB)，正在彻底清空..."
        )
        for item in workdir.iterdir():
            try:
                if item.is_file() or item.is_symlink():
                    item.unlink()
                elif item.is_dir():
                    shutil.rmtree(item)
            except (OSError, FileNotFoundError) as e:
                logger.error(f"❌ 清空时出错（跳过）: {item} - {e}")
        logger.info("✅ workdir 已彻底清空")
    else:
        logger.info("✅ workdir 大小正常，清理完成")