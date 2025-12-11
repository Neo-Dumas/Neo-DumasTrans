# core/block_renderers.py
import logging
from typing import Dict
from .text_renderer import render_text_content, render_code_content
# 导入拆分出去的模块
from .text_layout import TextLayoutSimulator
from .table_renderer import TableRenderer  # 新增导入

logger = logging.getLogger(__name__)


class IterativeFontSizeOptimizer:
    
    def __init__(self, default_font_size=12, max_iterations=10, tolerance=0.05, layout_simulator=None):
        self.default_font_size = default_font_size
        self.max_iterations = max_iterations
        self.tolerance = tolerance
        # 使用传入的 simulator，否则内部创建
        self.layout_simulator = layout_simulator or TextLayoutSimulator()

    def calculate_optimal_font_size(self, block, content, scale=1.0):
        bbox = block.get("bbox", [])
        if len(bbox) != 4 or not content.strip():
            return self.default_font_size

        x0, y0, x1, y1 = bbox
        container_width = (x1 - x0) * scale
        container_height = (y1 - y0) * scale

        # 目标高度：容器的90%
        target_height = container_height * 0.9

        # 👇 新增：打印容器宽度和文本内容
        display_content = content.strip()[:50] + ("..." if len(content.strip()) > 50 else "")
        logger.info(f"📐 容器宽度: {container_width:.1f}px | 容器高度: {container_height:.1f}px | 目标总高度: {target_height:.1f}px")
        logger.info(f"📝 正在处理文本: '{display_content}'")

        # 初始设置
        font_size = 1.0
        step = 10.0
        best_size = font_size
        prev_size = font_size

        # 第一阶段：快速上升，步长递减策略
        while step >= 1:
            layout = self.layout_simulator.simulate_text_layout(content, font_size, container_width)
            actual_height = layout['total_height']
            line_count = layout['line_count']

            # 新增详细调试日志
            logger.info(f"🔍 快速试探 | 字号: {font_size:.1f}px | 行数: {line_count} | 实际总高度: {actual_height:.1f}px / 目标: {target_height:.1f}px")

            if actual_height <= target_height:
                best_size = font_size
                font_size += step
            else:
                font_size -= step
                step = max(1.0, step / 2)
                font_size += step
                if step == 1.0:
                    break

        # 第二阶段：步长为1时的精细调整
        if step == 1.0:
            while True:
                layout = self.layout_simulator.simulate_text_layout(content, font_size, container_width)
                actual_height = layout['total_height']
                line_count = layout['line_count']

                # 新增详细调试日志
                logger.info(f"🔍 精细调整 | 字号: {font_size:.1f}px | 行数: {line_count} | 实际总高度: {actual_height:.1f}px / 目标: {target_height:.1f}px")

                if actual_height <= target_height:
                    best_size = font_size
                    prev_size = font_size
                    font_size += 1.0
                else:
                    if font_size > best_size:
                        candidate = font_size - 1.0
                        if candidate == best_size:
                            logger.info(f"🎯 减1后回到安全点 {candidate:.1f}px，采用它")
                            best_size = candidate
                        else:
                            layout_low = self.layout_simulator.simulate_text_layout(content, candidate, container_width)
                            if layout_low['total_height'] <= target_height:
                                logger.info(f"🎯 减1后 ({candidate:.1f}px) 满足，说明 {font_size:.1f}px 是首个超的，采用 {candidate:.1f}px")
                                best_size = candidate
                            else:
                                logger.info(f"⚠️ 减1后仍超，说明 {font_size - 2:.1f}px 是最后安全点")
                                best_size = font_size - 2.0
                        break
                    else:
                        break

        # 最终确保最小可读性
        final_size = max(best_size, 8.0)
        logger.info(f"✅ 优化完成 | 最终字号: {final_size:.1f}px")
        return round(final_size, 1)


class BlockRenderer:
    """基础块渲染器"""
    
    def __init__(self, layout_simulator=None):
        """
        初始化 BlockRenderer
        
        Args:
            layout_simulator: TextLayoutSimulator 实例，用于文本布局测量
                             如果未提供，则由 IterativeFontSizeOptimizer 内部创建
        """
        # 将 layout_simulator 传递给字体优化器
        self.font_optimizer = IterativeFontSizeOptimizer(
            layout_simulator=layout_simulator
        )
        self.table_renderer = TableRenderer(self.font_optimizer)  # 表格渲染器复用优化器
    
    def render(self, block: Dict, scale: float = 1.0) -> str:
        bbox = block.get("bbox")
        if not bbox or len(bbox) != 4:
            logger.warning(f"⚠️ Invalid bbox: {bbox}")
            return "<!-- Invalid bbox -->"

        x0, y0, x1, y1 = bbox
        block_type = block.get("type", "text")  # 默认也是 text

        # 提取 type 字段
        type1 = block.get("type1")
        type2 = block.get("type2")
        type3 = block.get("type3")

        # ================================
        # 语义类型白名单（只有这些值才被认为是有效的语义类）
        # 注意：现在只保留你真正想支持的语义类型
        # ================================
        VALID_SEMANTIC_TYPES = {
            "image_caption",
            "image_footnote",
            "table_caption",
            "table_footnote",
            "title",
            "index",
            "list",
            "interline_equation",
            "header",
            "footer",
            "page_number",
            "aside_text",
            "page_footnote",
            "code",
            "code_body",
            "code_caption", 
            "algorithm",
            # 可以继续添加...
        }

        # ================================
        # 新逻辑：依次检测 type1, type2, type3
        # 如果都不在白名单中，则使用 block["type"]
        # ================================
        cls = block_type  # 默认 fallback 到 type
        for t in (type1, type2, type3):
            if t and t in VALID_SEMANTIC_TYPES:
                cls = t
                break

        # 缩放坐标
        x0_s, y0_s = x0 * scale, y0 * scale
        width_s, height_s = (x1 - x0) * scale, (y1 - y0) * scale
        style = f'left:{x0_s}px;top:{y0_s}px;width:{width_s}px;height:{height_s}px;'

        # 根据类型分发渲染，并传递 cls 和 scale 参数
        inner = self._render_inner_content(block, block_type, cls, scale=scale)

        return f'<div class="block {cls}" style="{style}">{inner}</div>'
    
    def _render_inner_content(self, block: Dict, block_type: str, cls: str, scale: float = 1.0) -> str:
        """根据block类型渲染内部内容"""
        content = block.get("content", "")
        
        if block_type == "image":
            return self._render_image(block)
        elif block_type == "interline_equation":
            return self._render_equation(block)
        elif block_type == "table":
            # 使用专门的表格渲染器
            return self.table_renderer.render(block, scale=scale)
        elif block_type == "block_page":  # 👈 新增：空页面占位
            return '<div class="empty-page" style="width:100%;height:100%;background:transparent;"></div>'
        elif block_type == "text" or block_type == "inline_equation":  # 新增：行内公式也按文本处理
            return self._render_text(block, cls, scale=scale)
        else:
            return self._render_unknown(block_type)


    def _render_image(self, block: Dict) -> str:
        """渲染图片块"""
        img_path = block.get("image_path", "")
        return f'<img src="{img_path}" style="width:100%;height:100%;object-fit:contain;">'
    
    def _render_equation(self, block: Dict) -> str:
        """渲染独立公式块"""
        latex = block.get("content", "").strip()
        img_path = block.get("image_path")

        if latex:
            return f"<div class=\"interline-equation\">$${latex}$$</div>"
        elif img_path:
            return f'<img src="{img_path}" alt="Equation" style="width:100%;height:auto;">'
        else:
            return "<p style='color:#999;font-size:10px;'>[Equation missing]</p>"
    

    def _render_text(self, block: Dict, cls: str, scale: float = 1.0) -> str:
        """渲染文本块，代码和算法块保留原始格式"""
        content = block.get("content", "")
        type1 = block.get("type1")
        type2 = block.get("type2")
        type3 = block.get("type3")

        optimal_font_size = self.font_optimizer.calculate_optimal_font_size(block, content, scale)

        if cls in ["code", "algorithm"]:
            inner = render_code_content(
                content,
                type1=type1,
                type2=type2,
                type3=type3,
                font_size=optimal_font_size
            )
        else:
            # 👇 根据块类型决定外层标签：标题用 h1，其他用 div
            tag = "h1" if cls == "title" else "div"
            inner = render_text_content(
                content,
                type1=type1,
                type2=type2,
                type3=type3,
                font_size=optimal_font_size,
                tag=tag  # 传入标签类型
            )


        return inner
    
    def _render_unknown(self, block_type: str) -> str:
        """忽略未知类型块，不渲染任何内容"""
        logger.debug(f"Skipping unknown block type: '{block_type}'")
        return ""  # 或者直接 return ""