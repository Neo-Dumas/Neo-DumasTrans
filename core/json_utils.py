# core/json_utils.py
"""
工具函数：用于从扁平化的 JSON 列表中提取和写入文本内容。
支持结构化处理：根据 'type' 字段区分文本、公式等类型。
"""

from typing import List, Tuple, Any, Dict


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
    """
    # 定义要排除的类型集合（用于快速查找）
    excluded_types = {"code", "algorithm", "code_body", "code_caption", "interline_equation", "inline_equation"}

    blocks = []
    for idx, item in enumerate(data):
        content = item.get("content", "")
        if not isinstance(content, str):
            continue
        content = content.strip()

        block_type = item.get("type", "text")  # 默认为 "text"

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
    将翻译结果写回原始 JSON 结构中。

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
            print(f"[WARN] Index {idx} out of range during translation merge.")

    return result