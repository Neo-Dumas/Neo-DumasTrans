# core/local_translator.py
import time
import logging
import re
from pathlib import Path
from typing import List
import asyncio
from concurrent.futures import ThreadPoolExecutor
from llama_cpp import Llama
from .language_detector import (
    should_skip_translation,
    LANG_DISPLAY_MAP,
    detect_source_language,   # 保留用于其他用途（如日志）
    normalize_lang_code,
)
from .gpu_advisor import decide_n_gpu_layers_with_waiting
logger = logging.getLogger(__name__)

_LOCAL_MODEL_INSTANCE = None
_CACHED_MODEL_PATH = None
_LOCAL_TRANSLATOR_EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="LocalTranslator")


def get_local_model(model_path: str):
    global _LOCAL_MODEL_INSTANCE, _CACHED_MODEL_PATH
    if _LOCAL_MODEL_INSTANCE is not None and _CACHED_MODEL_PATH == model_path:
        return _LOCAL_MODEL_INSTANCE

    resolved_path = Path(model_path).resolve()
    if not resolved_path.exists():
        raise FileNotFoundError(f"本地模型未找到: {resolved_path}")

    logger.info(f"正在加载本地翻译模型: {resolved_path}")

    # ⭐ 关键：先等待60秒，再检测显存
    logger.info("等待60秒后再检测GPU显存...")
    time.sleep(60)

    # ⭐ 然后执行显存检测与 GPU 层数决策
    n_gpu_layers = decide_n_gpu_layers_with_waiting()

    try:
        _LOCAL_MODEL_INSTANCE = Llama(
            model_path=str(resolved_path),
            n_ctx=2048,
            n_threads=8,
            n_gpu_layers=n_gpu_layers,
            verbose=False
        )
        _CACHED_MODEL_PATH = model_path
        logger.info(f"本地模型加载完成 (n_gpu_layers={n_gpu_layers}).")
    except Exception as e:
        logger.error(f"加载本地模型失败: {e}")
        raise
    return _LOCAL_MODEL_INSTANCE


CHINESE_PROMPTS = [
    "把下面用三个反引号包裹的文本翻译成{target_lang_display}，不要任何解释，仅输出译文。\n\n```{text}```",
    "将```原文```翻译成{target_lang_display}，不要任何解释，仅输出```译文```。\n\n```{text}```",
    "将下列文本翻译成{target_lang_display}。\n\n```{text}```",
]


def contains_target_language(text: str, target_lang: str) -> bool:
    """
    判断文本中是否包含目标语言的典型字符。
    避免因 langdetect 对混合文本误判而拒绝有效译文。
    """
    if target_lang == "zh":
        return bool(re.search(r'[\u4e00-\u9fff]', text))
    elif target_lang == "ja":
        return bool(re.search(r'[\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff]', text))
    elif target_lang == "ko":
        return bool(re.search(r'[\uac00-\ud7af]', text))
    elif target_lang == "ru":
        return bool(re.search(r'[\u0400-\u04ff]', text))
    else:
        # 对于拉丁语系（en/fr/de/es 等），回退到 langdetect
        try:
            from langdetect import detect, LangDetectException
            detected = detect(text)
            return normalize_lang_code(detected) == normalize_lang_code(target_lang)
        except LangDetectException:
            return False


def translate_text_simple(text: str, target_lang: str, model_path: str) -> str:
    if not text.strip():
        return text

    skip, reason = should_skip_translation(text, target_lang)
    if skip:
        logger.debug(f"[跳过翻译] 原因: {reason} | 文本: {text[:50]}...")
        return text

    model = get_local_model(model_path)
    max_retries = 3
    MAX_RATIO = 1.5 if target_lang == "zh" else 3.0
    target_lang_display = LANG_DISPLAY_MAP.get(target_lang, target_lang)
    target_lang_norm = normalize_lang_code(target_lang)

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

            # === 后处理：提取核心译文 ===
            # 1. 双换行提取
            double_newline_match = re.search(r'\n\n(.*?)\n\n', translation, re.DOTALL)
            if double_newline_match:
                candidate = double_newline_match.group(1).strip()
                if candidate and len(candidate) >= 10:
                    translation = candidate
                    logger.debug(f"[双换行提取] 成功: {translation[:60]}...")

            # 2. 清理前缀
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

            # 3. 清理 ``` 包裹
            if translation.startswith("```") and translation.endswith("```"):
                translation = translation[3:-3].strip()
            elif translation.startswith("```"):
                lines = translation.split("\n", 1)
                if len(lines) > 1:
                    translation = lines[1].rstrip("```").strip()

            # 4. 提取 **...** 内容
            match = re.match(r'^\*\*([^*]+?)\*\*', translation)
            if match:
                extracted = match.group(1).strip()
                cleaned = re.sub(r'^[“‘"](.*)[”’"]$', r'\1', extracted)
                translation = cleaned.strip()
                logger.debug(f"[加粗提取] 成功: {translation}")

            if not translation:
                logger.warning(f"[本地翻译] 第{attempt + 1}次失败：译文为空")
                continue

            # === ✅ 新语言有效性检查：改为“目标语言存在性”判断 ===
            if contains_target_language(translation, target_lang_norm):
                # 语言特征匹配，再检查长度是否合理
                if len(text) > 0 and len(translation) > len(text) * MAX_RATIO:
                    logger.warning(
                        f"[本地翻译] 第{attempt + 1}次失败：译文过长 "
                        f"（原文{len(text)}字，译文{len(translation)}字，上限{MAX_RATIO}倍）: {translation[:60]}..."
                    )
                else:
                    logger.debug(f"[本地翻译] 成功（第{attempt + 1}次）: {translation[:50]}...")
                    return translation
            else:
                logger.warning(
                    f"[本地翻译] 第{attempt + 1}次失败：译文中未检测到目标语言 "
                    f"（期望: {target_lang_norm}）: {translation[:50]}..."
                )

        except Exception as e:
            logger.error(f"本地翻译失败 (attempt={attempt + 1}, text='{text[:30]}...'): {e}")

    logger.warning(f"[本地翻译] 三次尝试均失败，回退到原文: {text[:50]}...")
    return text


async def translate_text_list_locally(texts: List[str], target_lang: str, model_path: str) -> List[str]:
    loop = asyncio.get_running_loop()
    tasks = [
        loop.run_in_executor(_LOCAL_TRANSLATOR_EXECUTOR, translate_text_simple, text, target_lang, model_path)
        for text in texts
    ]
    return await asyncio.gather(*tasks)
