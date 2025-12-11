# core/batch_translator.py
import logging
from typing import List
import asyncio
from openai import AsyncOpenAI
import json
from .language_detector import should_skip_translation, LANG_DISPLAY_MAP

logger = logging.getLogger(__name__)


# --- 新增：底层单条翻译核心（无跳过逻辑）---
async def _translate_single_core(
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
    真正的单条翻译实现，假设输入 text 是必须翻译的。
    返回翻译结果或原样返回（如果模型出错？不，这里应抛异常或重试）
    """
    client = AsyncOpenAI(api_key=api_key, base_url=base_url)
    display_lang = LANG_DISPLAY_MAP.get(target_lang.lower(), target_lang)

    prompt = (
        f"请将以下文本翻译为 {display_lang}，仅输出译文，不要任何解释、前缀或后缀：\n\n"
        f"{text}"
    )

    for attempt in range(max_retries):
        try:
            response = await client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                timeout=timeout,
                max_tokens=min(512, max(128, len(text) * 2)),  # 动态调整
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.warning(f"Single translation failed (attempt {attempt + 1}): {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)  # 指数退避
            else:
                raise  # 最终失败时抛出，由上层处理

    # 不可达
    return text


# --- 修改：批量翻译主函数 ---
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
    if not texts:
        return []

    # Step 1: 预检跳过项
    skip_map = []
    input_items = []
    for idx, text in enumerate(texts):
        should_skip, reason = should_skip_translation(text, target_lang)
        skip_map.append(should_skip)
        if not should_skip:
            input_items.append({"id": idx, "text": text})
        else:
            logger.debug(f"Skipped translation [idx={idx}]: {reason} | Text: {repr(text[:50])}")

    if not input_items:
        return texts[:]

    client = AsyncOpenAI(api_key=api_key, base_url=base_url)
    display_lang = LANG_DISPLAY_MAP.get(target_lang.lower(), target_lang)

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
                messages=[{"role": "user", "content": full_prompt}],
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

                id_to_trans = {}
                for item in output_list:
                    if not isinstance(item, dict) or "id" not in item or "text" not in item:
                        raise ValueError("Each translation must have 'id' and 'text'")
                    trans_id = item["id"]
                    trans_text = item["text"]
                    if not isinstance(trans_id, int) or not isinstance(trans_text, str):
                        raise ValueError("Invalid id or text type")
                    id_to_trans[trans_id] = trans_text.strip()

                expected_ids = {item["id"] for item in input_items}
                if set(id_to_trans.keys()) != expected_ids:
                    raise ValueError(f"ID mismatch. Expected: {sorted(expected_ids)}, Got: {sorted(id_to_trans.keys())}")

                full_result = []
                for orig_idx, (is_skip, orig_text) in enumerate(zip(skip_map, texts)):
                    if is_skip:
                        full_result.append(orig_text)
                    else:
                        full_result.append(id_to_trans[orig_idx])

                # === 新增：DEBUG 输出成功解析的翻译 JSON ===
                if logger.isEnabledFor(logging.DEBUG):
                    try:
                        pretty_json = json.dumps(parsed, ensure_ascii=False, indent=2)
                        logger.debug(f"Successfully parsed translation response:\n{pretty_json}")
                    except Exception as dump_e:
                        logger.debug(f"Debug log failed to format response: {dump_e} | Raw: {content[:500]}")

                return full_result

            except (json.JSONDecodeError, ValueError, KeyError, TypeError) as e:
                logger.warning(f"Parse/validate failed (attempt {attempt + 1}): {e} | Content: {content[:200]}...")
                if attempt == max_retries - 1:
                    break

        except Exception as e:
            logger.warning(f"API call failed (attempt {attempt + 1}): {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(5 * (attempt + 1))

    # --- 修改：Fallback 使用 _translate_single_core，避免递归 ---
    logger.warning("Falling back to single-item translation after batch failure.")
    fallback_results = []
    for orig_idx, text in enumerate(texts):
        if skip_map[orig_idx]:
            fallback_results.append(text)
        else:
            try:
                trans = await _translate_single_core(
                    text=text,
                    target_lang=target_lang,
                    api_key=api_key,
                    base_url=base_url,
                    model_name=model_name,
                    max_retries=2,
                    timeout=timeout,
                    temperature=temperature,
                )
                fallback_results.append(trans)
            except Exception as e:
                logger.error(f"Single fallback failed for idx={orig_idx}: {e}. Using original text.")
                fallback_results.append(text)  # 最终兜底：用原文

    return fallback_results


# --- 修改：单条翻译入口（复用跳过逻辑 + 调用 core）---
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
    单条翻译入口：先判断是否跳过，否则调用核心翻译。
    """
    should_skip, reason = should_skip_translation(text, target_lang)
    if should_skip:
        logger.debug(f"Skipped single translation: {reason} | Text: {repr(text[:50])}")
        return text

    return await _translate_single_core(
        text=text,
        target_lang=target_lang,
        api_key=api_key,
        base_url=base_url,
        model_name=model_name,
        max_retries=max_retries,
        timeout=timeout,
        temperature=temperature,
    )