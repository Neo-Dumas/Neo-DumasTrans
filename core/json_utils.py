"""
工具函数：用于从扁平化的 JSON 列表中提取和写入文本内容。
支持结构化处理：根据 'type' 字段区分文本、公式、表格等类型。
"""

import logging
from typing import List, Tuple, Any, Dict
from xml.etree import ElementTree as ET
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


# ==============================
# 普通文本块处理
# ==============================

def extract_text_blocks(
    data: List[Dict[str, Any]]
) -> List[Tuple[int, Dict[str, str]]]:
    """
    提取所有文本块中的 type 和 content。

    Args:
        data: JSON 数据，格式为 List[Dict]，每个 dict 包含 'type' 和 'content' 字段

    Returns:
        列表，元素为 (索引, {"type": "...", "text": "..."})
        - 只有当 'content' 存在且为非空字符串，
          并且 'type', 'type1', 'type2', 'type3' 都不包含敏感类型时才提取
        - 注意：type == "table" 的项不会被提取（应通过 extract_table_cells 单独处理）
    """
    # 定义要排除的类型集合（用于快速查找）
    excluded_types = {
        "code", "algorithm", "code_body", "code_caption",
        "interline_equation", "inline_equation"
    }

    blocks = []
    for idx, item in enumerate(data):
        block_type = item.get("type", "text")

        # 跳过表格（由专用函数处理）
        if block_type == "table":
            continue

        content = item.get("content", "")
        if not isinstance(content, str):
            continue
        content = content.strip()

        # 检查 type, type1, type2, type3 是否包含任何被排除的类型
        types_to_check = [
            item.get("type"),
            item.get("type1"),
            item.get("type2"),
            item.get("type3")
        ]
        if any(t in excluded_types for t in types_to_check if isinstance(t, str)):
            continue  # 跳过这些类型

        # 只要 content 非空，就记录
        if content:
            blocks.append((idx, {
                "type": block_type,
                "text": content
            }))
    return blocks


def rebuild_json_with_translations(
    original_data: List[Dict[str, Any]],
    translation_map: Dict[int, str]
) -> List[Dict[str, Any]]:
    """
    将翻译结果写回原始 JSON 结构中（仅针对 'content' 字段）。

    Args:
        original_data: 原始 JSON 列表
        translation_map: 映射 {索引 -> 翻译后文本}

    Returns:
        新的列表，其中对应索引的 'content' 已被替换为翻译结果
    """
    # 浅拷贝整个列表和每个字典
    result = [{**item} for item in original_data]

    for idx, translated_text in translation_map.items():
        if 0 <= idx < len(result):
            result[idx]["content"] = translated_text
        else:
            logger.warning(f"Index {idx} out of range during translation merge.")

    return result


# ==============================
# 表格专用处理函数（使用 BeautifulSoup）
# ==============================

def extract_table_cells(data: List[Dict[str, Any]]) -> List[Tuple[int, List[str]]]:
    """
    从 type == "table" 的项中提取所有 <td>/<th> 内的文本。

    Args:
        data: JSON 数据列表

    Returns:
        列表，每个元素为 (index_in_data, [cell_text_1, cell_text_2, ...])
        - 仅当 html 字段存在且可解析时返回
        - 空单元格或纯空白单元格会被跳过（不加入列表）
    """
    table_entries = []
    for idx, item in enumerate(data):
        if item.get("type") != "table":
            continue
        html = item.get("html", "")
        if not isinstance(html, str) or not html.strip():
            continue

        texts, _ = _extract_texts_and_elements_from_html(html)
        if texts:  # 只有包含可翻译文本的表格才加入
            table_entries.append((idx, texts))
    return table_entries


def _extract_texts_and_elements_from_html(html: str) -> Tuple[List[str], list]:
    """
    使用 BeautifulSoup 安全解析 HTML 并提取 <td>/<th> 的文本和元素引用。
    返回 (texts: List[str], elements: List[Tag])
    """
    try:
        # 尝试直接解析
        soup = BeautifulSoup(html, "html.parser")
        table = soup.find("table")
        if table is None:
            # 如果没有 <table> 标签，尝试包裹
            wrapped = f"<table>{html}</table>"
            soup = BeautifulSoup(wrapped, "html.parser")
            table = soup.table

        if table is None:
            logger.warning("No table found even after wrapping.")
            return [], []

        texts = []
        elements = []
        for elem in table.find_all(["td", "th"]):
            text = elem.get_text(strip=True)
            if text:
                texts.append(text)
                elements.append(elem)
        return texts, elements
    except Exception as e:
        logger.error(f"Failed to parse table HTML: {e}")
        return [], []


def rebuild_table_html_with_translations(original_html: str, translated_texts: List[str]) -> str:
    """
    将翻译后的文本按顺序写回 HTML 表格，保持结构不变。
    使用 BeautifulSoup 实现安全重建。
    """
    try:
        texts, elements = _extract_texts_and_elements_from_html(original_html)
        if len(translated_texts) != len(texts):
            logger.warning(
                f"Translation length mismatch: expected {len(texts)}, got {len(translated_texts)}. "
                f"Original HTML snippet: {original_html[:150]}..."
            )
            return original_html

        # 替换每个单元格的文本内容
        for elem, trans in zip(elements, translated_texts):
            elem.clear()
            elem.string = trans  # 自动转义特殊字符

        # 判断原始是否是完整 <table>...</table>
        orig_stripped = original_html.strip()
        soup = elements[0].find_parent("table").find_parent() if elements else None
        table_tag = elements[0].find_parent("table") if elements else None

        if table_tag is None:
            return original_html

        # 重建 HTML 字符串
        new_table_html = str(table_tag)

        if orig_stripped.startswith("<table") and orig_stripped.endswith("</table>"):
            # 原始是完整 table，直接返回
            return new_table_html
        else:
            # 原始是片段，只返回 innerHTML
            return "".join(str(child) for child in table_tag.contents)

    except Exception as e:
        logger.error(f"Error rebuilding table HTML: {e}", exc_info=True)
        return original_html