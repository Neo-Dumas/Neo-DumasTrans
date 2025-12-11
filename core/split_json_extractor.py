
# core/split_json_extractor.py

import json
from pathlib import Path
from typing import Any, List, Dict, Optional, Union  # ✅ 确保包含 Union

from .block_merger import merge_vertical_blocks  # <-- 新增导入
import logging

# 配置日志（可选：在主程序中统一配置）
logger = logging.getLogger(__name__)


def is_bbox_like(obj: Any) -> bool:
    """判断对象是否为有效的 bbox [x0, y0, x1, y1]"""
    if not isinstance(obj, (list, tuple)) or len(obj) != 4:  # 支持 list 和 tuple
        return False
    return all(isinstance(x, (int, float)) and x >= 0 for x in obj)  # 增加坐标非负检查


def has_bbox(obj: Any) -> bool:
    """判断对象是否直接包含 bbox 字段"""
    if not isinstance(obj, dict):
        return False
    return "bbox" in obj and is_bbox_like(obj["bbox"])




def is_valid_bbox(value) -> bool:
    """检查 value 是否为有效的 bbox: 长度为4的 list/tuple，且每个元素为 int/float。"""
    if not isinstance(value, (list, tuple)):
        return False
    if len(value) != 4:
        return False
    return all(isinstance(x, (int, float)) for x in value)


def extract_leaf_bbox_blocks(
    obj: Any,
    current_page_info: Optional[Dict[str, Any]] = None,
    type_path: List[str] = None,
    bbox_path: List[Optional[List[float]]] = None
) -> List[Dict]:
    if type_path is None:
        type_path = []
    if bbox_path is None:
        bbox_path = []

    results = []
    context = {}
    if current_page_info:
        context.update(current_page_info)

    if isinstance(obj, dict):
        current_type = obj.get("type")
        raw_bbox = obj.get("bbox")
        has_valid_bbox = is_valid_bbox(raw_bbox)
        current_bbox = raw_bbox if has_valid_bbox else None

        new_type_path = type_path.copy()
        new_bbox_path = bbox_path.copy()
        if isinstance(current_type, str):
            new_type_path.append(current_type)
            new_bbox_path.append(current_bbox)

        # 判断是否有嵌套结构
        has_nested = False
        for value in obj.values():
            if isinstance(value, dict):
                has_nested = True
                break
            if isinstance(value, (list, tuple)):
                if any(isinstance(item, (dict, list)) for item in value):
                    has_nested = True
                    break

        is_leaf_level = not has_nested

        # ====== 保留：检查节点自身的页面信息（用于上下文注入）======
        has_own_page_idx = "page_idx" in obj
        has_own_page_size = (
            "page_size" in obj and 
            isinstance(obj["page_size"], (list, tuple)) and 
            len(obj["page_size"]) >= 2
        )
        
        # 更新页面上下文（仅当节点自身有页面信息时）
        if has_own_page_idx and has_own_page_size:
            context.update({
                "page_number": obj["page_idx"] + 1,
                "page_size": obj["page_size"][:2]
            })

        # ====== 判定逻辑：仅保留标准叶节点条件，删除空白页特殊提取 ======
        should_extract = False
        
        if is_leaf_level:
            # 删除了以下这行：
            # if has_own_page_idx:
            #     should_extract = True
            # 改为：只按标准条件提取
            should_extract = (
                isinstance(current_type, str) and 
                has_valid_bbox
            )

        if should_extract:
            extracted = dict(obj)

            # 确定祖先路径
            if isinstance(current_type, str):
                ancestor_types = new_type_path[:-1]
                ancestor_bboxes = new_bbox_path[:-1]
            else:
                ancestor_types = type_path
                ancestor_bboxes = bbox_path

            # 从父到根的顺序（反转祖先列表）
            for i, t in enumerate(reversed(ancestor_types), start=1):
                extracted[f"type{i}"] = t
            for i, bb in enumerate(reversed(ancestor_bboxes), start=1):
                extracted[f"bbox{i}"] = bb

            # 注入上下文（包括可能从祖先继承的页面信息）
            for k, v in context.items():
                if k not in extracted:
                    extracted[k] = v

            results.append(extracted)
        else:
            # 非叶级或不满足提取条件：递归子节点
            for value in obj.values():
                if isinstance(value, (dict, list)):
                    results.extend(
                        extract_leaf_bbox_blocks(value, context, new_type_path, new_bbox_path)
                    )

    elif isinstance(obj, list):
        for item in obj:
            results.extend(
                extract_leaf_bbox_blocks(item, context, type_path, bbox_path)
            )

    return results




def extract_leaf_blocks_from_file(
    json_path: Union[str, Path],
    pdf_type: Optional[str] = None
) -> bool:
    """
    从 middle.json 文件中提取最终的 leaf blocks，并输出为 {原文件名}_leaf_blocks.json。
    
    改进点：
        - 显式为每一页生成 block_page 块（基于 pdf_info 中的一级页面对象）
        - 叶级内容块通过 extract_leaf_bbox_blocks 提取（仅含有效内容）
        - 两者合并，确保页码完整、结构鲁棒
    
    pdf_type 行为：
        - "txt"/"ocr": 清理 para_blocks + 垂直合并内容块（跳过 block_page）
        - "vlm": 保留所有字段，不合并
        - 其他: 警告，按 vlm 处理
    """
    json_path = Path(json_path)
    if not json_path.exists():
        return False

    try:
        # 1. 读取原始中间文件
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # 2. 根据 pdf_type 决定是否清理 para_blocks（保持原逻辑）
        if pdf_type in ("txt", "ocr"):
            pdf_info = data.get("pdf_info", [])
            if isinstance(pdf_info, list):
                for page in pdf_info:
                    if isinstance(page, dict):
                        page.pop("para_blocks", None)
        elif pdf_type == "vlm":
            pass
        else:
            print(f"Warning: Unexpected pdf_type={pdf_type!r} for {json_path}. "
                  f"Treated as 'vlm'.")

        # === Step A: 显式提取所有页面元信息，生成 block_page 块 ===
        page_blocks = []
        pdf_info = data.get("pdf_info", [])
        if isinstance(pdf_info, list):
            for page_obj in pdf_info:
                if not isinstance(page_obj, dict):
                    continue
                page_idx = page_obj.get("page_idx")
                page_size = page_obj.get("page_size")
                
                
                if (
                    isinstance(page_idx, int) and
                    isinstance(page_size, (list, tuple)) and
                    len(page_size) >= 2 and
                    all(isinstance(x, (int, float)) and x >= 0 for x in page_size[:2])
                ):
                    width, height = page_size[0], page_size[1]
                    page_blocks.append({
                        "page_idx": page_idx,
                        "page_size": [width, height],
                        "page_number": page_idx + 1,
                        "bbox": [0, 0, width, height],
                        "bbox1": [0, 0, width, height], 
                        "type": "block_page",
                        "type1": "block_page",
                        "type2": "block_page",
                        "type3": "block_page"
                    })

        # === Step B: 使用修正后的 extract_leaf_bbox_blocks 提取内容叶块 ===
        # 此函数不再因 page_idx 提取空白页，但会正确传递 page_number 给子块
        leaf_content_blocks = extract_leaf_bbox_blocks(data)

        # === Step C: 合并页面块与内容块 ===
        leaf_blocks = page_blocks + leaf_content_blocks

        # 4. 对 txt/ocr 类型执行垂直合并（建议 merge_vertical_blocks 跳过 block_page）
        if pdf_type in ("txt", "ocr"):
            leaf_blocks = merge_vertical_blocks(leaf_blocks)

        # 5. 过滤 bbox 为 None 的块（主要是无效内容块，block_page 已保证有效）
        leaf_blocks = [
            block for block in leaf_blocks
            if not ("bbox" in block and block["bbox"] is None)
        ]

        # 6. 输出
        base_name = json_path.stem.removesuffix("_middle")
        output_path = json_path.parent / f"{base_name}_leaf_blocks.json"
        with open(output_path, "w", encoding="utf-8") as f_out:
            json.dump(leaf_blocks, f_out, ensure_ascii=False, indent=2)

        return True

    except Exception as e:
        print(f"Error processing {json_path}: {e}")
        return False