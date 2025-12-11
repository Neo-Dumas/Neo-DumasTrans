# core/language_detector.py
import re
from typing import Tuple
from langdetect import detect, LangDetectException

# 显示名映射
LANG_DISPLAY_MAP = {
    'zh': '中文',
    'en': '英语',
    'ja': '日语',
    'ko': '韩语',
    'fr': '法语',
    'de': '德语',
    'es': '西班牙语',
    'ru': '俄语',
}

# 正则表达式预编译（提升性能）
ROMAN_NUMERAL_PATTERN = re.compile(r'^(?=[MDCLXVI])M*(C[MD]|D?C{0,3})(X[CL]|L?X{0,3})(I[XV]|V?I{0,3})$', re.IGNORECASE)
GREEK_LETTER_PATTERN = re.compile(r'^[Α-Ωα-ω\u0370-\u03FF]+$')
NUMBER_PATTERN = re.compile(r'^[-+]?(\d+\.?\d*|\.\d+)([eE][-+]?\d+)?$')
ALPHANUMERIC_URL_EMAIL_PATTERN = re.compile(
    r'^https?://|www\..*\..*|[\w\.-]+@[\w\.-]+\.\w+$', re.IGNORECASE
)

# 极短英文白名单（可翻译但通常无需翻）
TRIVIAL_ENGLISH_WORDS = {
    "ok", "okay", "yes", "no", "hi", "hello", "bye", "thanks", "thank", "please",
    "on", "off", "up", "down", "in", "out", "go", "stop", "start", "end"
}

def normalize_lang_code(lang: str) -> str:
    lang = lang.lower().strip()
    if lang.startswith('zh'):
        return 'zh'
    return lang.split('-')[0]

def is_trivial_content(text: str) -> Tuple[bool, str]:
    """
    判断是否为“无需翻译”的 trivial 内容
    返回 (是否跳过, 原因)
    """
    stripped = text.strip()
    if not stripped:
        return True, "empty"

    # 1. 纯数字（整数、小数、科学计数法）
    if NUMBER_PATTERN.match(stripped.replace(',', '').replace(' ', '')):
        return True, "pure number"

    # 2. 罗马数字（仅由罗马字符组成且符合规则）
    if ROMAN_NUMERAL_PATTERN.match(stripped):
        return True, "roman numeral"

    # 3. 纯希腊字母（常用于公式）
    if GREEK_LETTER_PATTERN.match(stripped):
        return True, "greek letters"

    # 4. URL / 邮箱
    if ALPHANUMERIC_URL_EMAIL_PATTERN.match(stripped):
        return True, "url or email"

    # 5. 纯标点/符号（不含任何字母或汉字等）
    if not re.search(r'[a-zA-Z\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af\u0400-\u04ff]', stripped):
        # 没有拉丁字母、中日韩文字、西里尔字母等
        return True, "symbols only"

    # 6. 极短英文单词（≤3 字母 或 在白名单中）
    if re.fullmatch(r'[a-zA-Z]{1,3}', stripped):
        return True, "short english word (≤3 letters)"
    if stripped.lower() in TRIVIAL_ENGLISH_WORDS:
        return True, "trivial english word"

    return False, ""

def detect_source_language(text: str) -> str | None:
    try:
        return normalize_lang_code(detect(text))
    except LangDetectException:
        return None

def should_skip_translation(text: str, target_lang: str) -> Tuple[bool, str]:
    """
    综合判断是否跳过翻译：
    1. 先检查是否为 trivial 内容（数字、符号、短词等）→ 跳过
    2. 再检测语言，若已是目标语言 → 跳过
    3. 否则 → 不跳过
    """
    # 阶段1：Trivial 内容过滤
    is_trivial, reason = is_trivial_content(text)
    if is_trivial:
        return True, f"trivial content: {reason}"

    # 阶段2：语言匹配过滤
    target_norm = normalize_lang_code(target_lang)
    source_lang = detect_source_language(text.strip())

    if source_lang is None:
        # 无法检测语言：可能是噪声，但既然不是 trivial，保守送去翻译
        return False, "undetectable language – sending to translator"

    if source_lang == target_norm:
        display = LANG_DISPLAY_MAP.get(target_norm, target_norm)
        return True, f"already in {display}"

    return False, ""