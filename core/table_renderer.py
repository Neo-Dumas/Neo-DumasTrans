# core/table_renderer.py
import logging
from typing import Optional
from core.font_manager import FontManager

logger = logging.getLogger(__name__)

# 全局默认 FontManager 实例（单例模式）
_default_font_manager: Optional[FontManager] = None


def _get_global_font_manager() -> FontManager:
    """
    获取全局唯一的 FontManager 实例，避免重复初始化。
    """
    global _default_font_manager
    if _default_font_manager is None:
        _default_font_manager = FontManager()
        if not _default_font_manager.available:
            logger.warning(
                "⚠️ FontManager 初始化但字体可能不可用（Pillow 未安装或字体缺失），"
                "文本测量和渲染可能不准确。"
            )
    return _default_font_manager


class TableRenderer:
    """表格渲染器 - 使用外部注入的字体优化器和字体管理器"""

    def __init__(
        self,
        font_optimizer=None,
        font_manager: Optional[FontManager] = None
    ):
        if font_optimizer is None:
            raise ValueError("font_optimizer 必须传入。从 v2 起不再使用内置默认优化器。")

        self.table_font_optimizer = font_optimizer
        # 如果未传入 font_manager，使用全局默认实例
        self.font_manager: FontManager = font_manager or _get_global_font_manager()

        if not self.font_manager.available:
            logger.warning(
                "⚠️ 当前 FontManager 实例字体不可用，"
                "表格字体回退可能不准确。建议检查 DejaVuSans / NotoSansCJK 安装情况。"
            )

    def render(self, block: dict, scale: float = 1.0) -> str:
        table_html = block.get("html", "").strip()

        if not table_html:
            return '<div></div>'

        if table_html.startswith("<table"):
            # 使用外部传入的优化器计算基础字号
            base_font_size = self.table_font_optimizer.calculate_optimal_font_size(
                block, table_html, scale
            )

            # 放大系数可配置
            table_font_scale = 1.5
            optimal_font_size = base_font_size * table_font_scale
            optimal_font_size = max(1.0, min(optimal_font_size, 72.0))

            logger.info(f"📊 表格字号调整: 基础{base_font_size:.1f}px → 最终{optimal_font_size:.1f}px")

            # 智能选择字体族：基于表格中第一个可见字符
            font_family = self._detect_table_font_family(table_html)

            styled_table = self._apply_table_styles(table_html, optimal_font_size, font_family)

            return f'''
            <div style="width:100%; height:100%; padding:0px; box-sizing:border-box; 
                        display:flex; align-items:center; justify-content:center;
                        overflow:visible;">
                {styled_table}
            </div>
            '''

        # 可扩展其他情况
        return f'<div>{table_html}</div>'

    def _detect_table_font_family(self, table_html: str) -> str:
        """
        从表格 HTML 中提取第一个可见字符，判断应使用的 font-family。
        用于确保渲染时字体与 Pillow 测量时一致。
        """
        import re
        from html import unescape

        # 移除 HTML 标签，保留文本
        text_only = re.sub(r'<[^>]+>', '', table_html)
        text_only = unescape(text_only)  # 处理 &nbsp; 等实体

        # 遍历字符，找到第一个可打印字符
        for char in text_only:
            if char.isprintable() and not char.isspace():
                return self.font_manager.get_font_family(char)

        # 默认回退
        return self.font_manager.get_default_font_family()

    def _apply_table_styles(self, table_html: str, font_size: float, font_family: str) -> str:
        """
        为表格注入内联样式，强制宽度填满容器，并使用固定布局防止收缩。
        """
        style_attr = (
            f'style="'
            f'width:100%; '
            f'table-layout: auto; '  
            f'font-size: {font_size}px; '
            f'font-family: \'{font_family}\', sans-serif; '
            f'line-height: 1.0;"'
        )

        if "<table " in table_html:
            table_html = table_html.replace("<table ", f"<table {style_attr} ", 1)
        elif table_html.startswith("<table>"):
            table_html = table_html.replace("<table>", f'<table {style_attr}>', 1)

        return table_html