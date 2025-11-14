# core/text_renderer.py

import html
import re
from typing import Optional

def safe_html_escape(text: str) -> str:
    """安全转义 HTML，用于普通文本"""
    return html.escape(text or "", quote=False)

def render_mixed_math_content(content: str, font_size: int) -> str:
    """
    渲染混合数学内容：只对真正的公式部分使用MathJax，普通文本正常显示
    """
    # 识别行内公式模式：\(...\) 和 $...$
    math_pattern = r'(\\\(.*?\\\)|\$.*?\$)'
    
    parts = []
    last_end = 0
    
    for match in re.finditer(math_pattern, content):
        # 添加公式前的普通文本
        if match.start() > last_end:
            ordinary_text = content[last_end:match.start()]
            parts.append(('text', ordinary_text))
        
        # 添加公式部分
        formula = match.group(0)
        parts.append(('math', formula))
        last_end = match.end()
    
    # 添加剩余文本
    if last_end < len(content):
        ordinary_text = content[last_end:]
        parts.append(('text', ordinary_text))
    
    # 构建HTML
    html_parts = []
    for part_type, part_content in parts:
        if part_type == 'math':
            # 数学公式：用MathJax渲染
            html_parts.append(f'<span class="math-inline">{part_content}</span>')
        else:
            # 普通文本：安全转义
            html_parts.append(safe_html_escape(part_content))
    
    return ''.join(html_parts)

def render_text_content(
    content: str,
    type1: Optional[str] = None,
    type2: Optional[str] = None,
    type3: Optional[str] = None,
    font_size: Optional[int] = None
) -> str:
    """
    渲染文本内容。
    智能识别并只渲染真正的公式部分。
    """
    # 构建通用样式字符串
    style_parts = []
    if font_size is not None:
        style_parts.append(f"font-size:{font_size}px")
    
    style_parts.append("word-wrap: break-word")
    style_parts.append("overflow-wrap: break-word")
    style_parts.append("white-space: normal")
    style_parts.append("hyphens: auto")
    
    style_str = f' style="{"; ".join(style_parts)}"'

    if "inline_equation" in (type1, type2, type3):
        content = content.strip()
        
        # ✅ 智能渲染：只对真正的公式部分使用MathJax
        inner_html = render_mixed_math_content(content, font_size)
        return f'<div{style_str}>{inner_html}</div>'
    else:
        escaped_content = safe_html_escape(content)
        return f'<div{style_str}>{escaped_content}</div>'
    
def render_code_content(
    content: str,
    type1: Optional[str] = None,
    type2: Optional[str] = None,
    type3: Optional[str] = None,
    font_size: Optional[int] = None
) -> str:
    """用于代码/算法块，保留 pre 格式"""
    style = f"font-size:{font_size}px; white-space: pre; word-wrap: normal; overflow-wrap: normal; line-height: 1.2"
    
    if "inline_equation" in (type1, type2, type3):
        inner_html = render_mixed_math_content(content.strip(), font_size)
        return f'<div style="{style}">{inner_html}</div>'
    else:
        return f'<div style="{style}">{safe_html_escape(content)}</div>'