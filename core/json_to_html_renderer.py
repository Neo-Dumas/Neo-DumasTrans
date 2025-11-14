# core/json_to_html_renderer.py
import json
import logging
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Optional, Tuple, Any

from .block_renderers import BlockRenderer
from core.font_manager import FontManager
from core.text_layout import TextLayoutSimulator
from core.html_template import generate_full_html  # ✅ 使用统一模板

logger = logging.getLogger(__name__)

# ================================
# 全局初始化：字体与布局系统
# ================================

font_manager = FontManager()
if not font_manager.available:
    logger.error("❌ Pillow 未安装或字体加载失败，文本布局测量将不可用！")
    raise RuntimeError("Pillow and fonts are required for layout simulation.")

layout_simulator = TextLayoutSimulator(
    font_manager=font_manager,
    width_scale_factor=1.8
)
_renderer = BlockRenderer(layout_simulator=layout_simulator)

# ================================
# 常量定义
# ================================

CSS_DPI = 96
PDF_DPI = 72
SCALE_FACTOR = CSS_DPI / PDF_DPI  # ≈ 1.333，用于 pt → px 转换

# ================================
# 按页分组
# ================================

def group_blocks_by_page(blocks: List[Dict]) -> List[Dict[str, Any]]:
    """
    将 block 列表按 page_number 分组，生成页面列表。
    """
    pages = defaultdict(list)
    page_sizes = {}

    for block in blocks:
        page_num = block.get("page_number")
        if page_num is None:
            logger.warning(f"⚠️ Block missing 'page_number': {block.get('type')}")
            continue

        pages[page_num].append(block)

        if page_num not in page_sizes:
            page_size = block.get("page_size")
            if not page_size or len(page_size) < 2:
                raise ValueError(f"Page {page_num} missing valid 'page_size' in block: {block}")
            page_sizes[page_num] = page_size[:2]  # 宽, 高

    result = []
    for page_num in sorted(pages.keys()):
        result.append({
            "page_size": page_sizes[page_num],
            "blocks": pages[page_num]
        })
    return result

# ================================
# 渲染单个 block / 页面
# ================================

def render_block(block: Dict, scale: float = 1.0) -> str:
    """渲染单个 block 为 HTML 片段。"""
    try:
        return _renderer.render(block, scale)
    except Exception as e:
        logger.error(f"❌ Failed to render block {block.get('type')} (ID: {block.get('id')}): {e}")
        return ""

def render_page(page_data: Dict) -> str:
    """渲染单个页面为 HTML 字符串。"""
    page_size = page_data.get("page_size")
    if not page_size or len(page_size) < 2:
        raise ValueError(f"Invalid page_size: {page_size}")

    orig_w, orig_h = page_size[:2]
    scaled_w = orig_w * SCALE_FACTOR
    scaled_h = orig_h * SCALE_FACTOR

    blocks_html = []
    for block in page_data.get("blocks", []):
        html = render_block(block, SCALE_FACTOR)
        if html:
            blocks_html.append(html)

    return f"""
    <div class="pdf-page" style="width:{scaled_w}px; height:{scaled_h}px;">
        {''.join(blocks_html)}
    </div>
    """

# ================================
# 主接口：JSON → HTML（单文件）
# ================================

def render_json_to_html(input_json_path: str, output_html_path: str) -> Dict[str, Any]:
    """
    单文件渲染入口。

    Args:
        input_json_path (str): 输入 _translated.json 路径
        output_html_path (str): 输出 .html 路径

    Returns:
        Dict: {
            "success": bool,
            "output_path": str | None,
            "error": str | None
        }
    """
    input_path = Path(input_json_path)
    output_path = Path(output_html_path)

    try:
        # --- 1. 读取 CSS ---
        css_path = Path(__file__).parent / "css" / "pdf_renderer.css"
        try:
            with open(css_path, "r", encoding="utf-8") as f:
                css_content = f.read()
        except FileNotFoundError:
            error_msg = f"CSS 文件未找到: {css_path}"
            logger.error(f"❌ {error_msg}")
            return {"success": False, "output_path": None, "error": error_msg}
        except Exception as e:
            error_msg = f"读取 CSS 失败: {e}"
            logger.error(f"❌ {error_msg}")
            return {"success": False, "output_path": None, "error": error_msg}

        # --- 2. 读取 JSON ---
        if not input_path.exists():
            error_msg = f"输入 JSON 文件不存在: {input_path}"
            logger.error(f"❌ {error_msg}")
            return {"success": False, "output_path": None, "error": error_msg}

        with open(input_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, list):
            error_msg = "JSON 根节点必须是 block 列表"
            logger.error(f"❌ {error_msg}")
            return {"success": False, "output_path": None, "error": error_msg}

        if not data:
            error_msg = "JSON 中无有效 block 数据"
            logger.error(f"❌ {error_msg}")
            return {"success": False, "output_path": None, "error": error_msg}

        # --- 3. 分页并渲染 ---
        pages = group_blocks_by_page(data)
        if not pages:
            error_msg = "未生成任何有效页面（可能缺少 page_number）"
            logger.error(f"❌ {error_msg}")
            return {"success": False, "output_path": None, "error": error_msg}

        all_pages_html = "\n".join(render_page(page) for page in pages)

        # --- 4. 生成完整 HTML ---
        full_html = generate_full_html(
            body_content=all_pages_html,
            css_content=css_content,
            title=output_path.stem,
            mathjax_debug=False
        )

        # --- 5. 写入输出文件 ---
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(full_html)

        logger.info(f"✅ HTML 已生成: {output_path}")
        return {
            "success": True,
            "output_path": str(output_path),
            "error": None
        }

    except Exception as e:
        error_msg = f"渲染过程中发生异常: {type(e).__name__}: {e}"
        logger.error(f"❌ {error_msg}")
        return {
            "success": False,
            "output_path": None,
            "error": error_msg
        }

