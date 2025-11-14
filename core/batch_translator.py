# core/batch_translator.py
import logging
from typing import List, Optional, Dict, Any
import asyncio
from openai import AsyncOpenAI
import uuid
import re
import json
from .language_detector import should_skip_translation, LANG_DISPLAY_MAP

logger = logging.getLogger(__name__)


async def translate_text_list_as_json(
    texts: List[str],
    target_lang: str,
    api_key: str,
    base_url: str,
    model_name: str,
    max_retries: int = 3,
    timeout: int = 120,
    temperature: float = 0.1,
) -> List[str]:
    """
    使用结构化 JSON 输入/输出进行批量翻译：
    - 输入：[{"id": 0, "text": "原文1"}, {"id": 1, "text": "原文2"}, ...]
    - 输出：{"translations": [{"id": 0, "text": "译文1"}, {"id": 1, "text": "译文2"}, ...]}
    - 通过 id 保证顺序，彻底避免错乱。
    """
    if not texts:
        return []

    # Step 1: 预检跳过项
    skip_map = []
    input_items = []  # [{"id": int, "text": str}]
    for idx, text in enumerate(texts):
        should_skip, _ = should_skip_translation(text, target_lang)
        skip_map.append(should_skip)
        if not should_skip:
            input_items.append({"id": idx, "text": text})

    if not input_items:
        return texts[:]

    client = AsyncOpenAI(api_key=api_key, base_url=base_url)
    display_lang = LANG_DISPLAY_MAP.get(target_lang.lower(), target_lang)

    # Step 2: 构造结构化 prompt（单轮对话，无 system/user 区分）
    input_json_str = json.dumps(input_items, ensure_ascii=False, indent=2)
    full_prompt = (
        f"你将收到一个 JSON 列表，其中每个对象包含一个唯一整数 `id` 和待翻译的 `text`。\n"
        f"请将所有 `text` 翻译为 **{display_lang}**，并返回一个 JSON 对象：\n"
        f'{{"translations": [{{"id": 0, "text": "译文"}}, ...]}}\n\n'
        f"要求：\n"
        f"- 保持 `id` 不变，仅翻译 `text`\n"
        f"- 输出必须是合法 JSON，且 `translations` 列表长度与输入完全一致\n"
        f"- 不要添加任何额外字段、解释或 Markdown\n\n"
        f"输入数据：\n{input_json_str}"
    )

    for attempt in range(max_retries):
        try:
            response = await client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": full_prompt}],  # 单轮对话
                temperature=temperature,
                timeout=timeout,
                max_tokens=8192,
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content.strip()

            try:
                parsed = json.loads(content)
                output_list = parsed.get("translations", [])
                if not isinstance(output_list, list):
                    raise ValueError("translations is not a list")

                # 构建 id -> translation 映射
                id_to_trans = {}
                for item in output_list:
                    if not isinstance(item, dict) or "id" not in item or "text" not in item:
                        raise ValueError("Each translation must have 'id' and 'text'")
                    trans_id = item["id"]
                    trans_text = item["text"]
                    if not isinstance(trans_id, int) or not isinstance(trans_text, str):
                        raise ValueError("Invalid id or text type")
                    id_to_trans[trans_id] = trans_text.strip()

                # 验证所有输入 id 都有对应输出
                expected_ids = {item["id"] for item in input_items}
                if set(id_to_trans.keys()) != expected_ids:
                    raise ValueError(f"ID mismatch. Expected: {sorted(expected_ids)}, Got: {sorted(id_to_trans.keys())}")

                # 重建完整结果（按原始 texts 顺序）
                full_result = []
                for orig_idx, (is_skip, orig_text) in enumerate(zip(skip_map, texts)):
                    if is_skip:
                        full_result.append(orig_text)
                    else:
                        full_result.append(id_to_trans[orig_idx])

                return full_result

            except (json.JSONDecodeError, ValueError, KeyError, TypeError) as e:
                logger.warning(f"Parse/validate failed (attempt {attempt + 1}): {e} | Content: {content[:200]}...")
                if attempt == max_retries - 1:
                    break

        except Exception as e:
            logger.warning(f"API call failed (attempt {attempt + 1}): {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(5 * (attempt + 1))

    # Fallback to single translation
    logger.warning("Falling back to single-item translation after batch failure.")
    fallback_tasks = []
    for text in texts:
        should_skip, _ = should_skip_translation(text, target_lang)
        if should_skip:
            fallback_tasks.append(asyncio.create_task(asyncio.sleep(0, result=text)))
        else:
            fallback_tasks.append(asyncio.create_task(translate_single_text(
                text=text,
                target_lang=target_lang,
                api_key=api_key,
                base_url=base_url,
                model_name=model_name,
                temperature=temperature,
                timeout=timeout,
                max_retries=2
            )))
    return await asyncio.gather(*fallback_tasks)


async def translate_single_text(
    text: str,
    target_lang: str,
    api_key: str,
    base_url: str,
    model_name: str,
    max_retries: int = 3,
    timeout: int = 120,
    temperature: float = 0.1,
) -> str:
    """
    单条翻译，内部复用批量 JSON 模式逻辑，确保行为一致。
    """
    # 直接调用批量函数，传入单元素列表
    result_list = await translate_text_list_as_json(
        texts=[text],
        target_lang=target_lang,
        api_key=api_key,
        base_url=base_url,
        model_name=model_name,
        max_retries=max_retries,
        timeout=timeout,
        temperature=temperature,
    )
    return result_list[0]

