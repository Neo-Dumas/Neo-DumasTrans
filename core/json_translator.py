# core\json_translator.py

import logging
from pathlib import Path
from typing import Dict, Any, List
import json
import asyncio
from copy import deepcopy

from core.json_utils import extract_text_blocks, rebuild_json_with_translations
from core.batch_translator import translate_single_text, translate_text_list_as_json
from core.local_translator import translate_text_list_locally

logger = logging.getLogger(__name__)


def _bboxes_equal(bbox1, bbox2, tol=1e-5):
    """判断两个 bbox 是否相等（考虑浮点误差）"""
    if len(bbox1) != 4 or len(bbox2) != 4:
        return False
    return all(abs(a - b) < tol for a, b in zip(bbox1, bbox2))


async def _translate_group_with_semaphore(
    group_idx: int,
    group: List[Dict],
    target_lang: str,
    api_key: str,
    base_url: str,
    model_name: str,
    item_to_index: Dict[int, int],
    semaphore: asyncio.Semaphore,
):
    async with semaphore:  # 限制并发
        # 分离需要翻译的文本项
        text_to_translate = [
            item for item in group
            if item.get("type") == "text" and item["text"].strip()
        ]

        # 初始化结果容器（只针对本组）
        group_translations = {}

        # 非翻译项直接回填原文
        for item in group:
            if item not in text_to_translate:
                idx = item_to_index[id(item)]
                group_translations[idx] = item["text"]

        if not text_to_translate:
            return group_translations

        expected_count = len(text_to_translate)
        try:
            translated_batch = await _translate_and_validate(
                items=text_to_translate,
                target_lang=target_lang,
                api_key=api_key,
                base_url=base_url,
                model_name=model_name,
                expected_count=expected_count,
                batch_id=group_idx
            )
        except Exception as e:
            logger.warning(f"Group {group_idx} failed: {e}. Falling back to single-item mode.")
            translated_batch = []
            for item in text_to_translate:
                try:
                    tr = await translate_single_text(
                        text=item["text"],
                        target_lang=target_lang,
                        api_key=api_key,
                        base_url=base_url,
                        model_name=model_name,
                    )
                    translated_batch.append(tr)
                except Exception as ex:
                    logger.error(f"Single fallback failed for: {item['text'][:50]}... Error: {ex}")
                    translated_batch.append(item["text"])

        # 回填本组翻译结果
        for item, trans in zip(text_to_translate, translated_batch):
            idx = item_to_index[id(item)]
            group_translations[idx] = trans

        await asyncio.sleep(1)  # 避免 API 限流（可选）
        return group_translations



def merge_inline_equations(blocks):
    """
    在翻译完成后，合并具有相同 bbox 且属于同一页的连续行内公式块。
    - 仅当 type == 'inline_equation' 时，content 被包裹为 $...$
    - 其他文本块直接拼接
    - 仅连续、同页、且 bbox 相同的块才合并
    - 返回新列表，不修改原数据
    """
    if not blocks:
        return []

    results = []
    i = 0
    n = len(blocks)

    while i < n:
        current = blocks[i]

        # 只处理包含字符串 content 的块
        if "content" not in current or not isinstance(current["content"], str):
            results.append(deepcopy(current))
            i += 1
            continue

        current_page = current.get("page_number")

        # 收集后续连续、同页、相同 bbox 且 content 为字符串的块
        group = [current]
        j = i + 1
        while j < n:
            candidate = blocks[j]
            candidate_page = candidate.get("page_number")

            # 新增条件：必须同页
            if (
                "content" in candidate
                and isinstance(candidate["content"], str)
                and candidate_page == current_page
                and _bboxes_equal(current["bbox"], candidate["bbox"])
            ):
                group.append(candidate)
                j += 1
            else:
                break

        if len(group) > 1:
            merged_content_parts = []
            for item in group:
                content = item["content"]
                if item.get("type") == "inline_equation":
                    merged_content_parts.append(f"${content}$")
                else:
                    merged_content_parts.append(content)
            merged_content = "".join(merged_content_parts)

            merged_block = deepcopy(current)
            merged_block["content"] = merged_content
            results.append(merged_block)
            i = j  # 跳过已合并的块
        else:
            results.append(deepcopy(current))
            i += 1

    return results


def _group_texts_by_char_limit(items: List[Dict], char_limit: int = 500) -> List[List[Dict]]:
    """
    将 items 按 content 字数动态分组，每组总字数 ≤ char_limit。
    注意：只统计 type == 'text' 且非空的文本字数。
    非文本或空文本单独成组，避免干扰计数。
    """
    groups = []
    current_group = []
    current_chars = 0

    for item in items:
        if item.get("type") != "text" or not item["text"].strip():
            # 非文本或空文本：立即提交当前组（如有），然后单独成组
            if current_group:
                groups.append(current_group)
                current_group = []
                current_chars = 0
            groups.append([item])
            continue

        text_len = len(item["text"])
        if current_group and current_chars + text_len > char_limit:
            groups.append(current_group)
            current_group = [item]
            current_chars = text_len
        else:
            current_group.append(item)
            current_chars += text_len

    if current_group:
        groups.append(current_group)

    return groups


async def _translate_and_validate(
    items: List[Dict],
    target_lang: str,
    api_key: str,
    base_url: str,
    model_name: str,
    expected_count: int,
    batch_id: int,
    max_retries: int = 1
) -> List[str]:
    texts = [item["text"] for item in items]

    for attempt in range(max_retries + 1):
        try:
            result = await translate_text_list_as_json(
                texts=texts,
                target_lang=target_lang,
                api_key=api_key,
                base_url=base_url,
                model_name=model_name,
                max_retries=2,
                timeout=120,
                temperature=0.1
            )

            if len(result) == expected_count:
                return result
            else:
                logger.warning(f"Batch {batch_id} attempt {attempt + 1}: length mismatch")
        except Exception as e:
            logger.warning(f"Batch {batch_id} attempt {attempt + 1} failed: {e}")

        if attempt < max_retries:
            await asyncio.sleep(3)

    raise RuntimeError(f"Batch {batch_id} failed after {max_retries + 1} attempts")


async def _translate_json_data(
    json_data: Dict[str, Any],
    target_lang: str,
    api_key: str,
    base_url: str,
    model_name: str,
    file_path: str,
    concurrency: int = 10,
    char_limit_per_batch: int = 1500
) -> Dict[str, Any]:
    text_items = extract_text_blocks(json_data)
    if not text_items:
        return json_data

    indices, items = zip(*text_items)
    indices = list(indices)
    items = list(items)
    texts = [item["text"] for item in items]

    logger.info(f"Translating {len(texts)} text blocks from {file_path}")

    # ✅ 修改：只要 base_url 是 "local"，就视为本地模式，model_name 即为模型路径
    if base_url == "local":
        logger.info(f"检测到本地翻译模式，使用模型路径: {model_name}")
        translated_texts = await translate_text_list_locally(texts, target_lang, model_path=model_name)
    else:
        # 原有在线 API 逻辑
        text_groups = _group_texts_by_char_limit(items, char_limit=char_limit_per_batch)
        logger.info(f"Split into {len(text_groups)} dynamic batches (char limit={char_limit_per_batch})")

        translated_texts = [""] * len(items)
        item_to_index = {id(item): idx for idx, item in enumerate(items)}
        semaphore = asyncio.Semaphore(concurrency)

        tasks = [
            _translate_group_with_semaphore(
                group_idx=idx,
                group=group,
                target_lang=target_lang,
                api_key=api_key,
                base_url=base_url,
                model_name=model_name,
                item_to_index=item_to_index,
                semaphore=semaphore,
            )
            for idx, group in enumerate(text_groups)
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Group translation failed: {result}")
                continue
            for idx, trans in result.items():
                translated_texts[idx] = trans

    # 重建 JSON
    translation_map = dict(zip(indices, translated_texts))
    translated_data = rebuild_json_with_translations(json_data, translation_map)
    return translated_data


async def translate_single_json_file(
    input_path: Path,
    output_path: Path,
    target_lang: str,
    api_key: str,
    base_url: str,
    model_name: str,
    concurrency: int = 10,
    char_limit_per_batch: int = 1500,
) -> str:
    """
    主程序调用的单文件翻译接口。
    流程：读取 → 翻译（动态分批+校验+回退） → 合并公式 → 写出
    """
    input_path = Path(input_path)
    output_path = Path(output_path)

    if not input_path.exists():
        raise FileNotFoundError(f"输入文件不存在: {input_path}")

    # 如果输出文件已存在，跳过
    if output_path.exists():
        logger.info(f"跳过已翻译文件: {output_path}")
        return str(output_path)

    try:
        logger.info(f"【调试】并发数参数: {concurrency}, 字数限制: {char_limit_per_batch}")
        with open(input_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # 第一步：执行翻译（此时不合并公式）
        translated_data = await _translate_json_data(
            json_data=data,
            target_lang=target_lang,
            api_key=api_key,
            base_url=base_url,
            model_name=model_name,
            file_path=str(input_path),
            concurrency=concurrency, 
            char_limit_per_batch=char_limit_per_batch,
        )

        # 第二步：翻译完成后，合并行内公式
        translated_data = merge_inline_equations(translated_data)

        # 确保输出目录存在
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # 写出最终翻译+合并后的结果
        with open(output_path, 'w', encoding='utf-8') as f_out:
            json.dump(translated_data, f_out, ensure_ascii=False, indent=2)

        logger.info(f"✅ 翻译完成: {output_path}")
        return str(output_path)

    except Exception as e:
        logger.error(f"翻译失败 {input_path} → {output_path}: {e}", exc_info=True)
        raise