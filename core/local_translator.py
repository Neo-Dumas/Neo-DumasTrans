# core/local_translator.py

import logging
import re
from pathlib import Path
from typing import List
import asyncio
from concurrent.futures import ThreadPoolExecutor
from llama_cpp import Llama
from .language_detector import (
    should_skip_translation,
    is_char_in_ranges,
    LANGUAGE_UNICODE_RANGES,
    LANG_DISPLAY_MAP,  # ✅ 直接引用已有映射
)

logger = logging.getLogger(__name__)

_LOCAL_MODEL_INSTANCE = None
_CACHED_MODEL_PATH = None

# 创建一个单线程的专用执行器（只允许一个翻译任务运行）
_LOCAL_TRANSLATOR_EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="LocalTranslator")

def get_local_model(model_path: str):
    global _LOCAL_MODEL_INSTANCE, _CACHED_MODEL_PATH

    if _LOCAL_MODEL_INSTANCE is not None and _CACHED_MODEL_PATH == model_path:
        return _LOCAL_MODEL_INSTANCE

    resolved_path = Path(model_path).resolve()
    if not resolved_path.exists():
        raise FileNotFoundError(f"本地模型未找到: {resolved_path}")

    logger.info(f"正在加载本地翻译模型: {resolved_path}")
    try:
        _LOCAL_MODEL_INSTANCE = Llama(
            model_path=str(resolved_path),
            n_ctx=4096,
            n_threads=8,
            n_gpu_layers=50,
            verbose=False
        )
        _CACHED_MODEL_PATH = model_path
        logger.info("本地模型加载完成。")
    except Exception as e:
        logger.error(f"加载本地模型失败: {e}")
        raise

    return _LOCAL_MODEL_INSTANCE


# ✅ 只保留一套中文提示模板，使用 {target_lang_display}
CHINESE_PROMPTS = [
    "把下面用三个反引号包裹的文本翻译成{target_lang_display}，不要任何解释，仅输出译文。\n\n```{text}```",
    "将```原文```翻译成{target_lang_display}，不要任何解释，仅输出```译文```。\n\n```{text}```",
    "将下列文本翻译成{target_lang_display}。\n\n```{text}```",
]


def translate_text_simple(text: str, target_lang: str, model_path: str) -> str:
    if not text.strip():
        return text

    skip, reason = should_skip_translation(text, target_lang)
    if skip:
        logger.debug(f"[跳过翻译] 原因: {reason} | 文本: {text[:50]}...")
        return text

    model = get_local_model(model_path)
    max_retries = 3

    # ✅ 动态设置最大长度容忍倍数
    MAX_RATIO = 1.5 if target_lang == "zh" else 3.0

    # ✅ 直接使用 language_detector 中的 LANG_DISPLAY_MAP
    target_lang_display = LANG_DISPLAY_MAP.get(target_lang, target_lang)

    for attempt in range(max_retries):
        template = CHINESE_PROMPTS[attempt % len(CHINESE_PROMPTS)]
        prompt = template.format(target_lang_display=target_lang_display, text=text)

        try:
            output = model.create_completion(
                prompt=prompt,
                max_tokens=min(2048, int(len(text) * 3)),
                temperature=0.0,
                top_p=0.95,
                repeat_penalty=1.1,
                echo=False,
                stream=False
            )

            translation = output["choices"][0]["text"].strip()

            # === 新增：提取 \n\n...\n\n 中间的核心译文（优先处理）===
            double_newline_match = re.search(r'\n\n(.*?)\n\n', translation, re.DOTALL)
            if double_newline_match:
                candidate = double_newline_match.group(1).strip()
                # 仅当提取内容非空且有一定长度时才采纳（避免提取注释或空段）
                if candidate and len(candidate) >= 10:
                    translation = candidate
                    logger.debug(f"[双换行提取] 成功提取核心译文: {translation[:60]}...")

            # 清理可能的前后缀
            prefixes_to_remove = [
                "译文：", "翻译：", "译文:", "翻译:",
                "Translation:", "Translated:", "Output:", "Result:",
                "以下是翻译后的中文内容：",
                "（原文此处内容不完整，无法继续翻译。）", 
                "以下是使用三个反引号包裹的文本的简体中文翻译：",
                "以下是翻译后的文本：",
                "以下是中文翻译：",
                "（注：部分术语为专有名词或历史事件，翻译时采用保留原名的方式。）",
            ]
            for prefix in prefixes_to_remove:
                if translation.startswith(prefix):
                    translation = translation[len(prefix):].strip()
                    break

            # 清理 ``` 包裹
            if translation.startswith("```") and translation.endswith("```"):
                translation = translation[3:-3].strip()
            elif translation.startswith("```"):
                lines = translation.split("\n", 1)
                if len(lines) > 1:
                    translation = lines[1].rstrip("```").strip()

            # 尝试提取开头的 **...** 内容（仅当存在时）
            match = re.match(r'^\*\*([^*]+?)\*\*', translation)
            if match:
                extracted = match.group(1).strip()
                # 移除首尾的中英文引号（支持 “” ‘’ ""）
                cleaned = re.sub(r'^[“‘"](.*)[”’"]$', r'\1', extracted)
                translation = cleaned.strip()
                logger.debug(f"[加粗提取] 提取成功: {translation}")

            # 语言有效性检查：是否包含目标语言字符
            target_ranges = LANGUAGE_UNICODE_RANGES.get(target_lang)

            if target_ranges is None:
                logger.debug(f"[语言未知] 跳过检测，视为有效: {target_lang}")
                return translation

            has_target_char = any(is_char_in_ranges(char, target_ranges) for char in translation)

            if has_target_char:
                # 动态长度检查：中文严格（1.5倍），其他语言宽松（3倍）
                if len(text) > 0 and len(translation) > len(text) * MAX_RATIO:
                    logger.warning(
                        f"[本地翻译] 第{attempt + 1}次失败：译文含目标语言但过长 "
                        f"（原文{len(text)}字，译文{len(translation)}字，上限{MAX_RATIO}倍），疑似解释: {translation[:60]}..."
                    )
                else:
                    logger.debug(f"[本地翻译] 成功（第{attempt + 1}次）: {translation[:50]}...")
                    return translation
            else:
                logger.warning(
                    f"[本地翻译] 第{attempt + 1}次失败：译文不含目标语言 '{target_lang}'，内容: {translation[:50]}..."
                )

        except Exception as e:
            logger.error(f"本地翻译失败 (attempt={attempt + 1}, text='{text[:30]}...', model={model_path}): {e}")

    # 三次均失败：回退到原文
    logger.warning(f"[本地翻译] 三次尝试均失败，回退到原文: {text[:50]}...")
    return text


async def translate_text_list_locally(texts: List[str], target_lang: str, model_path: str) -> List[str]:
    loop = asyncio.get_running_loop()
    tasks = [
        loop.run_in_executor(
            _LOCAL_TRANSLATOR_EXECUTOR,
            translate_text_simple,
            text,
            target_lang,
            model_path
        )
        for text in texts
    ]
    results = await asyncio.gather(*tasks)
    return results