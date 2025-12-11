#core\text_layout.py

from typing import Dict, List
import logging
import re
from PIL import ImageFont  # 确保 Pillow 已安装

from .math_measurer import MathMeasurer
from .math_formula import MathFormulaProcessor
from core.font_manager import FontManager  

logger = logging.getLogger(__name__)

class TextLayoutSimulator:
    """文本布局模拟器：使用 Pillow 实际测量字符宽度，支持中英文、数学公式混合布局"""

    def __init__(self, font_manager: FontManager, width_scale_factor: float = 1.0):
        self.font_manager = font_manager
        self.font_metrics = {
            'line_height_ratio': 1.2,  # 行高系数（Pillow 不直接提供行高）
        }
        self.math_measurer = MathMeasurer()
        self.formula_processor = MathFormulaProcessor()
        self._char_width_cache = {}  # 字符宽度缓存: (char, font_size) -> width

        # 👉 新增：宽度缩放系数，用于校正整体测量偏差
        self.width_scale_factor = width_scale_factor

    def simulate_text_layout(self, content: str, font_size: float, container_width: float) -> Dict:
        if not content.strip():
            return {'lines': [], 'line_count': 0, 'total_height': 0, 'max_width': 0}
        
        words = self.split_into_words(content)
        lines = []
        current_line = []
        current_line_width = 0
        
        for word in words:
            word_width = self.calculate_word_width(word, font_size)
            
            if not current_line or current_line_width + word_width <= container_width:
                current_line.append(word)
                current_line_width += word_width
            else:
                lines.append(''.join(current_line))
                current_line = [word]
                current_line_width = word_width
        
        if current_line:
            lines.append(''.join(current_line))
        
        line_height = font_size * self.font_metrics['line_height_ratio']
        total_height = len(lines) * line_height
        
        max_width = 0
        for line in lines:
            line_width = self.calculate_text_width(line, font_size)
            max_width = max(max_width, line_width)
        
        return {
            'lines': lines,
            'line_count': len(lines),
            'total_height': total_height,
            'max_width': min(max_width, container_width)
        }

    def split_into_words(self, text: str) -> List[str]:
        words = []
        current_word = ""
        i = 0
        while i < len(text):
            char = text[i]
            math_match = None
            for pattern in [r'\\\(.*?\\\)', r'\$.*?\$', r'\\\[.*?\\\]']:
                match = re.match(pattern, text[i:])
                if match:
                    math_match = match
                    break
            
            if math_match:
                if current_word:
                    words.append(current_word)
                    current_word = ""
                formula = math_match.group(0)
                words.append(formula)
                i += len(formula)
                continue
            
            if char.isspace():
                if current_word:
                    words.append(current_word)
                    current_word = ""
                words.append(char)
            elif self.is_chinese(char):
                if current_word:
                    words.append(current_word)
                words.append(char)
                current_word = ""
            elif char.isalnum():
                if current_word and (self.is_chinese(current_word[-1]) or current_word[-1].isspace()):
                    words.append(current_word)
                    current_word = char
                else:
                    current_word += char
            else:
                if current_word:
                    words.append(current_word)
                    current_word = ""
                words.append(char)
            
            i += 1
        
        if current_word:
            words.append(current_word)
        
        return words
    
    def is_chinese(self, char: str) -> bool:
        return '\u4e00' <= char <= '\u9fff'
    
    def calculate_word_width(self, word: str, font_size: float) -> float:
        if self.formula_processor.is_math_formula(word):
            return self.calculate_math_width(word, font_size)
        
        total_width = 0.0
        for char in word:
            char_width = self._get_char_width(char, int(font_size))
            total_width += char_width
        return total_width

    def _get_char_font(self, char: str, font_size: int) -> ImageFont.ImageFont:
        if (
            char.isalnum() or
            '\u0370' <= char <= '\u03FF' or  
            '\u2200' <= char <= '\u22FF' or 
            '\u27C0' <= char <= '\u27EF' or 
            char in '+-=<>/*()[]{}|\\^~!@#$%^&*_.,;:?'
        ):
            return self.font_manager.get_math_font(font_size)
        if '\u4e00' <= char <= '\u9fff':
            return self.font_manager.get_cjk_font(font_size)
        return self.font_manager.get_script_font(font_size)

    def _get_char_width(self, char: str, font_size: int) -> float:
        key = (char, font_size)
        if key in self._char_width_cache:
            return self._char_width_cache[key]
        
        font = self._get_char_font(char, font_size)
        bbox = font.getbbox(char, anchor="ls")
        raw_width = bbox[2] - bbox[0]

        # 👉 应用宽度缩放系数
        scaled_width = raw_width * self.width_scale_factor
        self._char_width_cache[key] = scaled_width
        return scaled_width

    def calculate_math_width(self, formula: str, font_size: float) -> float:
        measured_width = self.math_measurer.measure_math_formula(formula, font_size)
        if measured_width is not None:
            logger.debug(f"📏 Pillow measured formula width: {measured_width:.1f}px for: {formula}")
            # 👉 应用宽度缩放系数
            return measured_width * self.width_scale_factor
        logger.debug(f"🔄 Falling back to heuristic math width calculation for: {formula}")
        heuristic_width = self.math_measurer.calculate_math_width_heuristic(formula, font_size)
        # 👉 启发式结果也应用系数
        return heuristic_width * self.width_scale_factor
        
    def calculate_text_width(self, text: str, font_size: float) -> float:
        return self.calculate_word_width(text, font_size)