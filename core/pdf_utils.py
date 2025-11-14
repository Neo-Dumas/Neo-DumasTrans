# core/pdf_utils.py
import logging
from collections import Counter
import fitz  
from typing import Tuple, Optional, List, Dict, Any, Set

logger = logging.getLogger(__name__)

def rgb_to_tuple(rgb: Tuple[float, float, float]) -> Tuple[float, float, float]:
    """将 RGB 颜色元组四舍五入到小数点后 3 位，便于哈希统计"""
    return tuple(round(c, 3) for c in rgb)

def is_light_color(rgb: Tuple[float, float, float]) -> bool:
    """
    判断颜色是否为“浅色”（适合作为背景）
    使用人眼感知亮度公式：0.299R + 0.587G + 0.114B
    """
    r, g, b = rgb
    brightness = 0.299 * r + 0.587 * g + 0.114 * b
    return brightness > 0.7

def get_background_color_from_page(
    page: fitz.Page,
    rect: fitz.Rect,
    sample_margin: float = 10.0,
    zoom: float = 2.0
) -> Tuple[float, float, float]:
    """
    从页面中采样 bbox 周围的颜色，估算背景色
    - 优先采样 bbox 外围的像素（上下左右边框外）
    - 只保留浅色，排除文字/线条等深色
    - 返回最常见的浅色，若无则返回默认浅灰
    """
    mat = fitz.Matrix(zoom, zoom)
    try:
        pix = page.get_pixmap(matrix=mat)
    except Exception as e:
        logger.warning(f"无法获取页面图像用于颜色采样: {e}")
        return (0.9, 0.9, 0.9)  # fallback

    img_data = pix.samples_mv
    stride = pix.stride
    width = pix.width
    height = pix.height

    def to_img_coord(x: float, y: float) -> Tuple[int, int]:
        return int(x * zoom), int(y * zoom)

    x0_img, y0_img = to_img_coord(rect.x0, rect.y0)
    x1_img, y1_img = to_img_coord(rect.x1, rect.y1)

    colors = []

    margin = int(sample_margin * zoom)
    search_rects = [
        (x0_img - margin, y0_img - margin, x1_img + margin, y0_img),
        (x0_img - margin, y1_img, x1_img + margin, y1_img + margin),
        (x0_img - margin, y0_img + margin, x0_img, y1_img - margin),
        (x1_img, y0_img + margin, x1_img + margin, y1_img - margin),
    ]

    for rx0, ry0, rx1, ry1 in search_rects:
        rx0 = max(0, rx0)
        ry0 = max(0, ry0)
        rx1 = min(width, rx1)
        ry1 = min(height, ry1)

        step = max(1, (rx1 - rx0) // 10)
        for y in range(ry0, ry1, 2):
            for x in range(rx0, rx1, step):
                idx = y * stride + x * 3
                if idx + 2 < len(img_data):
                    r, g, b = img_data[idx], img_data[idx + 1], img_data[idx + 2]
                    rgb = (r / 255.0, g / 255.0, b / 255.0)
                    if is_light_color(rgb):
                        colors.append(rgb_to_tuple(rgb))

    if colors:
        color_count = Counter(colors)
        most_common = color_count.most_common(1)[0][0]
        return most_common

    return (0.9, 0.9, 0.9)

def organize_boxes(blocks: List[Dict[str, Any]], target_types: Set[str], is_code_related_func) -> Tuple[Dict[int, List[fitz.Rect]], int]:
    page_boxes = {}
    skipped_count = 0
    for block in blocks:
        if not isinstance(block, dict):
            continue

        block_type = block.get("type")
        if block_type not in target_types:
            skipped_count += 1
            continue

        if block_type == "text" and is_code_related_func(block):
            skipped_count += 1
            continue

        if "bbox" not in block or "page_number" not in block:
            continue
        page_num = block["page_number"] - 1  # 0-indexed
        bbox = block["bbox"]
        if len(bbox) != 4:
            continue
        x0, y0, x1, y1 = bbox
        page_boxes.setdefault(page_num, []).append(fitz.Rect(x0, y0, x1, y1))
    
    return page_boxes, skipped_count