import logging
from typing import Optional

try:
    from PIL import Image, ImageDraw
    PILLOW_AVAILABLE = True
except ImportError:
    PILLOW_AVAILABLE = False

from .font_manager import FontManager
from .math_formula import MathFormulaProcessor

logger = logging.getLogger(__name__)

class MathMeasurer:
    """数学公式测量器"""
    
    def __init__(self):
        self.font_manager = FontManager()
        self.formula_processor = MathFormulaProcessor()
        self.available = PILLOW_AVAILABLE
    
    def measure_math_formula(self, formula: str, font_size: float) -> Optional[float]:
        """测量数学公式宽度"""
        if not self.available:
            return None
            
        try:
            clean_formula = self.formula_processor.clean_formula(formula)
            if not clean_formula:
                logger.debug(f"🔍 清理后公式为空，原公式: {formula}")
                return None
                
            logger.debug(f"🔍 测量公式: '{formula}' -> 清理后: '{clean_formula}', 字号: {font_size}px")
            
            # 使用新的get_math_font方法获取用于数学公式的字体
            font = self.font_manager.get_math_font(font_size)
            if font is None:
                return None
                
            # 创建临时图像进行测量
            dummy_img = Image.new('RGB', (1, 1))
            draw = ImageDraw.Draw(dummy_img)
            
            # 测量公式文本尺寸
            bbox = draw.textbbox((0, 0), clean_formula, font=font)
            width = bbox[2] - bbox[0]
            
            # 应用复杂度补偿
            compensated_width = self._apply_complexity_compensation(width, clean_formula)
            
            # 设置合理的宽度限制
            final_width = self._apply_width_limits(compensated_width, font_size)
            
            logger.debug(f"🔍 公式测量结果: 原始{width:.1f}px -> 最终{final_width:.1f}px")
            
            return final_width
            
        except Exception as e:
            logger.warning(f"Pillow measurement failed for formula: {formula}, error: {e}")
            import traceback
            logger.debug(f"详细错误信息: {traceback.format_exc()}")
            return None
    
    def _apply_complexity_compensation(self, width: float, clean_formula: str) -> float:
        """应用复杂度补偿"""
        math_compensation = 0.5  # 基础补偿系数
        complexity_factor = 1.0
        complexity_factors = []
        
        # 上下标检测
        if '^' in clean_formula or '_' in clean_formula:
            complexity_factor *= 0.7
            complexity_factors.append("上下标(0.7)")
        
        # 分数检测
        if '\\frac' in clean_formula or '/' in clean_formula:
            complexity_factor *= 0.9
            complexity_factors.append("分数(0.9)")
        
        # 大型运算符检测
        large_operators = ['∑', '∫', '∏', '∬', '∭', '∮']
        if any(op in clean_formula for op in large_operators):
            complexity_factor *= 1.15
            complexity_factors.append("大型运算符(1.15)")
        
        # 根号检测
        if '\\sqrt' in clean_formula:
            complexity_factor *= 0.95
            complexity_factors.append("根号(0.95)")
        
        # 积分/求和上下限检测
        if ('∫' in clean_formula or '∑' in clean_formula) and ('_' in clean_formula or '^' in clean_formula):
            complexity_factor *= 0.85
            complexity_factors.append("积分求和上下限(0.85)")
        
        # 简单表达式检测
        simple_chars = len([c for c in clean_formula if c.isalnum() or c in '+-=()'])
        total_chars = len(clean_formula)
        if total_chars > 0 and simple_chars / total_chars > 0.8:
            complexity_factor *= 0.7
            complexity_factors.append("简单表达式(0.7)")
        
        # 多层括号检测
        bracket_depth = self._calculate_max_bracket_depth(clean_formula)
        if bracket_depth >= 2:
            complexity_factor *= 1.1
            complexity_factors.append(f"多层括号(1.1):深度{bracket_depth}")
        
        compensated_width = width * math_compensation * complexity_factor
        
        logger.debug(f"🔍 公式复杂度分析: 因子{complexity_factor:.3f}, 因素{complexity_factors}")
        
        return compensated_width
    
    def _calculate_max_bracket_depth(self, text: str) -> int:
        """计算最大括号深度"""
        bracket_depth = 0
        max_bracket_depth = 0
        for char in text:
            if char in '([{':
                bracket_depth += 1
                max_bracket_depth = max(max_bracket_depth, bracket_depth)
            elif char in ')]}':
                bracket_depth -= 1
        return max_bracket_depth
    
    def _apply_width_limits(self, width: float, font_size: float) -> float:
        """应用宽度限制"""
        max_formula_width = font_size * 25
        min_formula_width = font_size * 2
        return max(min_formula_width, min(width, max_formula_width))
    
    def calculate_math_width_heuristic(self, formula: str, font_size: float) -> float:
        """启发式数学公式宽度计算（回退方法）"""
        clean_formula = self.formula_processor.clean_formula(formula)
        if not clean_formula:
            return font_size * 2
        
        # 基础宽度计算
        base_width = len(clean_formula) * font_size * 0.5
        
        # 复杂度因子
        complexity = 1.0
        if '^' in clean_formula or '_' in clean_formula:
            complexity *= 1.0
        if '\\frac' in clean_formula or '/' in clean_formula:
            complexity *= 1.1
        if '∑' in clean_formula or '∫' in clean_formula or '∏' in clean_formula:
            complexity *= 1.2
        if '\\sqrt' in clean_formula:
            complexity *= 1.1
        
        estimated_width = base_width * complexity
        
        # 宽度限制
        max_formula_width = font_size * 25
        min_formula_width = font_size * 3
        
        return max(min_formula_width, min(estimated_width, max_formula_width))