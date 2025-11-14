# core/language_detector.py
import re
from typing import List

# 语言码到自然语言描述的映射
LANG_DISPLAY_MAP = {
    'zh': '简体中文',
    'zh-cn': '简体中文',
    'zh-tw': '繁体中文',
    'en': '英语',
    'ja': '日语',
    'ko': '韩语',
    'fr': '法语',
    'de': '德语',
    'es': '西班牙语',
    'ru': '俄语',
    # 可扩展
}

# 语言 Unicode 范围定义
LANGUAGE_UNICODE_RANGES = {
    'zh': [  # 中文
        (0x4E00, 0x9FFF),      # CJK统一表意文字
        (0x3400, 0x4DBF),      # CJK扩展A
        (0x20000, 0x2A6DF),    # CJK扩展B
        (0x2A700, 0x2B73F),    # CJK扩展C
        (0x2B740, 0x2B81F),    # CJK扩展D
        (0x2B820, 0x2CEAF),    # CJK扩展E
        (0x2CEB0, 0x2EBEF),    # CJK扩展F
        (0x3007, 0x3007),      # 〇
    ],
    'zh-cn': [  # 简体中文（同中文）
        (0x4E00, 0x9FFF),
        (0x3400, 0x4DBF),
        (0x20000, 0x2A6DF),
        (0x2A700, 0x2B73F),
        (0x2B740, 0x2B81F),
        (0x2B820, 0x2CEAF),
        (0x2CEB0, 0x2EBEF),
        (0x3007, 0x3007),
    ],
    'zh-tw': [  # 繁体中文（同中文）
        (0x4E00, 0x9FFF),
        (0x3400, 0x4DBF),
        (0x20000, 0x2A6DF),
        (0x2A700, 0x2B73F),
        (0x2B740, 0x2B81F),
        (0x2B820, 0x2CEAF),
        (0x2CEB0, 0x2EBEF),
        (0x3007, 0x3007),
    ],
    'ja': [  # 日语
        (0x4E00, 0x9FFF),      # 汉字
        (0x3040, 0x309F),      # 平假名
        (0x30A0, 0x30FF),      # 片假名
        (0x31F0, 0x31FF),      # 片假名拼音扩展
        (0xFF66, 0xFF9F),      # 半角片假名
    ],
    'ko': [  # 韩语
        (0xAC00, 0xD7AF),      # 谚文音节
        (0x1100, 0x11FF),      # 谚文字母
        (0x3130, 0x318F),      # 谚文兼容字母
    ],
    'en': [  # 英语
        (0x0041, 0x005A),      # 大写字母 A-Z
        (0x0061, 0x007A),      # 小写字母 a-z
    ],
    'fr': [  # 法语（拉丁字母扩展）
        (0x0041, 0x005A),
        (0x0061, 0x007A),
        (0x00C0, 0x00FF),      # 拉丁字母补充-1
    ],
    'de': [  # 德语
        (0x0041, 0x005A),
        (0x0061, 0x007A),
        (0x00C0, 0x00FF),
    ],
    'es': [  # 西班牙语
        (0x0041, 0x005A),
        (0x0061, 0x007A),
        (0x00C0, 0x00FF),
    ],
    'ru': [  # 俄语
        (0x0400, 0x04FF),      # 西里尔字母
        (0x0500, 0x052F),      # 西里尔字母补充
    ],
}


def is_char_in_ranges(char: str, ranges: list) -> bool:
    """检查字符是否在指定的Unicode范围内"""
    code_point = ord(char)
    for start, end in ranges:
        if start <= code_point <= end:
            return True
    return False


def is_already_target_language(text: str, target_lang: str) -> bool:
    """
    检测文本中目标语言字符是否在"所有有意义的文字字符"中占比超过 50%
    排除标点、空格、控制字符等
    """
    if not text.strip():
        return False
    
    target_ranges = LANGUAGE_UNICODE_RANGES.get(target_lang.lower())
    if not target_ranges:
        return False

    # 统计：目标语言字符数 + 所有其他语言文字字符数
    target_char_count = 0
    total_meaningful_chars = 0  # 所有有意义的文字字符（排除标点、空格等）

    for char in text:
        code_point = ord(char)
        
        # 判断该字符是否属于任何语言的文字系统（至少在一个语言范围内）
        is_meaningful = False
        
        for lang, ranges in LANGUAGE_UNICODE_RANGES.items():
            if is_char_in_ranges(char, ranges):
                is_meaningful = True
                break
        
        if not is_meaningful:
            continue  # 忽略标点、空格、制表符、特殊符号等
        
        total_meaningful_chars += 1
        
        # 如果这个有意义字符属于目标语言
        if is_char_in_ranges(char, target_ranges):
            target_char_count += 1

    # 没有任何有意义文字？→ 不是目标语言
    if total_meaningful_chars == 0:
        return False

    # 目标语言占比 > 50%
    return (target_char_count / total_meaningful_chars) > 0.5


def has_meaningful_english(text: str) -> bool:
    """
    检测是否有有意义的英文内容（连续字母>=3个）
    """
    # 查找连续字母序列
    english_sequences = re.findall(r'[a-zA-Z]{3,}', text)
    
    # 如果有任意连续字母序列长度>=3，认为有英文内容
    return len(english_sequences) > 0


def has_any_text_content(text: str) -> bool:
    """
    检测文本是否包含任何有意义的文字内容
    包括：中文、日文、韩文、英文(连续>=3个字母)等
    """
    if not text.strip():
        return False
    
    # 检查是否有中文/日文/韩文字符
    for lang_ranges in LANGUAGE_UNICODE_RANGES.values():
        for char in text:
            if is_char_in_ranges(char, lang_ranges):
                return True
    
    # 检查是否有有意义的英文内容
    if has_meaningful_english(text):
        return True
    
    return False


def should_skip_translation(text: str, target_lang: str) -> tuple[bool, str]:
    """
    判断是否应该跳过翻译，返回 (是否跳过, 跳过原因)
    
    优化后的过滤逻辑：
    1. 空文本
    2. 无任何文字内容（纯标点、数字、符号等）
    3. Unicode比例检测：目标语言字符占比 > 50%
    4. 英文内容检测：对于英文目标，检查是否有连续英文>=3个
    """
    stripped_text = text.strip()
    
    # 1. 空文本检测
    if not stripped_text:
        return True, "empty text"
    
    # 2. 文字内容检测：没有任何有意义的文字内容
    if not has_any_text_content(stripped_text):
        return True, "no meaningful text content"
    
    # 3. Unicode比例检测：已经是目标语言
    if is_already_target_language(stripped_text, target_lang):
        return True, f"already in {target_lang} (unicode ratio > 50%)"
    
    # 4. 英文内容检测：对于英文目标，检查是否有有意义的英文
    if target_lang.lower() in ['en', 'english']:
        if not has_meaningful_english(stripped_text):
            return True, "no meaningful english content (continuous letters < 3)"
    
    return False, ""