# core/font_manager.py
import logging
from typing import Dict, Optional

try:
    from PIL import ImageFont
    PILLOW_AVAILABLE = True
except ImportError:
    PILLOW_AVAILABLE = False

logger = logging.getLogger(__name__)


class FontManager:
    """
    字体管理器：严格分离字体用途，避免混用
    - DejaVuSans: 英文、数字、基础拉丁、希腊字母、数学符号等
    - NotoSans: 小语种（俄文、阿拉伯文等非 CJK 且非拉丁及希腊的文字）
    - NotoSansCJK: 中日韩汉字

    ✅ 提供字体实例（用于 Pillow 测量）
    ✅ 提供字体族名（用于 HTML/CSS 渲染）
    """

    # 👉 字体类型到 CSS font-family 名称的映射
    FONT_FAMILY_MAP = {
        "math": "DejaVuSans",
        "script": "NotoSans",
        "cjk": "NotoSansCJK",
    }

    def __init__(self):
        self.available = PILLOW_AVAILABLE

        # 各字体缓存：type -> size -> font
        self._math_cache: Dict[int, ImageFont.ImageFont] = {}  # 数学相关（含拉丁字母、数字、希腊字母等）
        self._script_cache: Dict[int, ImageFont.ImageFont] = {}  # scripts (non-CJK and non-math)
        self._cjk_cache: Dict[int, ImageFont.ImageFont] = {}

        # 明确路径优先级
        self._font_paths = {
            "math": [
                "fonts/DejaVuSans.ttf",
                "./fonts/DejaVuSans.ttf",
                "DejaVuSans.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            ],
            "script": [
                "fonts/NotoSans-Regular.ttf",
                "./fonts/NotoSans-Regular.ttf",
                "NotoSans-Regular.ttf",
                "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
            ],
            "cjk": [
                "fonts/NotoSansCJK-Regular.ttc",
                "./fonts/NotoSansCJK-Regular.ttc",
                "NotoSansCJK-Regular.ttc",
                "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
            ]
        }

    def get_math_font(self, font_size: int) -> Optional[ImageFont.ImageFont]:
        """
        获取数学相关字体（DejaVuSans）：英文、数字、基础拉丁、希腊字母、数学符号等
        """
        return self._get_cached_font("math", font_size, self._math_cache)

    def get_script_font(self, font_size: int) -> Optional[ImageFont.ImageFont]:
        """
        获取小语种字体（Noto Sans）：俄文、阿拉伯文等
        """
        return self._get_cached_font("script", font_size, self._script_cache)

    def get_cjk_font(self, font_size: int) -> Optional[ImageFont.ImageFont]:
        """
        获取中日韩字体（Noto Sans CJK）
        """
        return self._get_cached_font("cjk", font_size, self._cjk_cache)

    def _get_cached_font(
        self,
        font_type: str,
        font_size: int,
        cache: Dict[int, ImageFont.ImageFont]
    ) -> Optional[ImageFont.ImageFont]:
        """通用缓存获取逻辑"""
        if not self.available:
            return None

        size_key = int(font_size)
        if size_key in cache:
            return cache[size_key]

        font = self._load_specific_font(font_type, size_key)
        if font:
            cache[size_key] = font
            logger.debug(f"✅ 加载 {font_type} 字体成功 | 大小: {size_key}px")
        else:
            logger.warning(f"❌ 无法加载 {font_type} 字体 | 请求大小: {size_key}px")

        return font

    def _load_specific_font(self, font_type: str, font_size: int) -> Optional[ImageFont.ImageFont]:
        paths = self._font_paths.get(font_type, [])
        for path in paths:
            try:
                font = ImageFont.truetype(path, font_size)
                return font
            except Exception as e:
                continue

        # 最后尝试系统默认（仍可能不支持特定文字）
        try:
            logger.warning(f"⚠️ {font_type} 字体未找到，使用默认字体 | 大小: {font_size}px")
            return ImageFont.load_default()
        except Exception as e:
            logger.error(f"❌ 加载默认字体失败: {e}")
            return None

    def get_font_family(self, char: str) -> str:
        """
        根据字符返回应使用的 CSS font-family 名称。
        用于确保 HTML 渲染时使用的字体与 Pillow 测量时一致。

        Args:
            char: 单个字符

        Returns:
            font-family 名称，如 "DejaVuSans", "NotoSansCJK" 等
        """
        if not char:
            return self.get_default_font_family()

        c = ord(char)
        # 数学/拉丁/数字/希腊/符号
        if (
            char.isalnum() or
            0x0370 <= c <= 0x03FF or  # 希腊字母和科普特字母
            0x2200 <= c <= 0x22FF or  # 数学符号
            0x27C0 <= c <= 0x27EF or  # 数学符号扩展-A
            char in '+-=<>/*()[]{}|\\^~!@#$%^&*_.,;:?'
        ):
            return self.FONT_FAMILY_MAP["math"]
        # 中日韩汉字
        if 0x4E00 <= c <= 0x9FFF or 0x3400 <= c <= 0x4DBF or \
           0x20000 <= c <= 0x2A6DF or 0x2A700 <= c <= 0x2B73F or \
           0x2B740 <= c <= 0x2B81F or 0x2B820 <= c <= 0x2CEAF or \
           0xF900 <= c <= 0xFAFF or 0x2F800 <= c <= 0x2FA1F:
            return self.FONT_FAMILY_MAP["cjk"]
        # 其他脚本（俄文、阿拉伯文等）
        return self.FONT_FAMILY_MAP["script"]

    def get_default_font_family(self) -> str:
        """
        返回默认使用的字体族名称。
        推荐用于无内容或无法判断时。
        """
        return self.FONT_FAMILY_MAP["cjk"]  # 默认使用 CJK 字体，适合中文场景

    def clear_cache(self):
        """清空所有字体缓存"""
        self._math_cache.clear()
        self._script_cache.clear()
        self._cjk_cache.clear()
        logger.debug("🗑️ 字体缓存已清空")