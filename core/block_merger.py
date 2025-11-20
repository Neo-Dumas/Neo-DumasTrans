import copy
from typing import List, Dict


def merge_vertical_blocks(
    blocks: List[Dict],
    float_eps: float = 1e-5,
) -> List[Dict]:
    """
    合并条件：
    - 相邻块同 type 和 bbox1
    额外处理：
    - 删除 type 为 "text" 且 content 字段为纯空白字符串（如 "  ", "\n\t " 等）的块。
    - 类型为 "image"、"table"、"interline_equation"、"block_page" 的块不参与合并，单独保留。
    """

    if not blocks:
        return []

    # 定义不应合并的类型
    NON_MERGEABLE_TYPES = {"image", "table", "interline_equation", "block_page"}

    # 过滤：仅当 type 为 "text" 且 content 是纯空白字符串时才删除
    filtered_blocks = [
        block for block in blocks
        if not (
            block.get("type") == "text" and
            isinstance(block.get("content"), str) and
            block["content"].strip() == ""
        )
    ]

    if not filtered_blocks:
        return []

    result_blocks = []
    current_block = copy.deepcopy(filtered_blocks[0])
    current_content = str(current_block.get("content", ""))
    current_bbox1 = current_block.get("bbox1")
    current_type = current_block.get("type")

    for next_block in filtered_blocks[1:]:
        next_bbox1 = next_block.get("bbox1")
        next_type = next_block.get("type")

        # 判断是否可以合并：两个块都不能是不可合并类型，且满足 bbox1 和 type 相同
        can_merge = (
            current_type not in NON_MERGEABLE_TYPES and
            next_type not in NON_MERGEABLE_TYPES and
            next_bbox1 is not None and current_bbox1 is not None and
            abs(next_bbox1[0] - current_bbox1[0]) < float_eps and
            abs(next_bbox1[1] - current_bbox1[1]) < float_eps and
            abs(next_bbox1[2] - current_bbox1[2]) < float_eps and
            abs(next_bbox1[3] - current_bbox1[3]) < float_eps and
            next_type == current_type
        )

        if can_merge:
            current_content += " " + str(next_block.get("content", ""))
        else:
            # 保存当前合并块（或单个不可合并块）
            current_block["content"] = current_content
            current_block["bbox"] = current_bbox1
            # 清理多余的 bboxn 字段（只保留 'bbox'）
            keys_to_remove = [k for k in current_block if k.startswith('bbox') and k != 'bbox']
            for k in keys_to_remove:
                del current_block[k]
            result_blocks.append(current_block)

            # 开始新块
            current_block = copy.deepcopy(next_block)
            current_content = str(next_block.get("content", ""))
            current_bbox1 = next_bbox1
            current_type = next_type

    # 处理最后一个块
    current_block["content"] = current_content
    current_block["bbox"] = current_bbox1
    keys_to_remove = [k for k in current_block if k.startswith('bbox') and k != 'bbox']
    for k in keys_to_remove:
        del current_block[k]
    result_blocks.append(current_block)

    return result_blocks