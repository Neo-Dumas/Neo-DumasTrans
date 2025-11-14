import re
import logging
from typing import Dict

logger = logging.getLogger(__name__)

class MathFormulaProcessor:
    """数学公式处理器"""
    
    def __init__(self):
        self.latex_to_unicode = self._build_latex_to_unicode_map()
    
    def _build_latex_to_unicode_map(self) -> Dict[str, str]:
        """构建 LaTeX 到 Unicode 的转换表"""
        return {
            # 希腊字母
            '\\alpha': 'α', '\\beta': 'β', '\\gamma': 'γ', '\\delta': 'δ',
            '\\epsilon': 'ε', '\\zeta': 'ζ', '\\eta': 'η', '\\theta': 'θ',
            '\\iota': 'ι', '\\kappa': 'κ', '\\lambda': 'λ', '\\mu': 'μ',
            '\\nu': 'ν', '\\xi': 'ξ', '\\pi': 'π', '\\rho': 'ρ',
            '\\sigma': 'σ', '\\tau': 'τ', '\\upsilon': 'υ', '\\phi': 'φ',
            '\\chi': 'χ', '\\psi': 'ψ', '\\omega': 'ω',
            # 大写希腊字母
            '\\Gamma': 'Γ', '\\Delta': 'Δ', '\\Theta': 'Θ', '\\Lambda': 'Λ',
            '\\Xi': 'Ξ', '\\Pi': 'Π', '\\Sigma': 'Σ', '\\Upsilon': 'Υ',
            '\\Phi': 'Φ', '\\Psi': 'Ψ', '\\Omega': 'Ω',
            # 数学运算符
            '\\sum': '∑', '\\int': '∫', '\\prod': '∏', '\\partial': '∂',
            '\\nabla': '∇', '\\infty': '∞', '\\pm': '±', '\\mp': '∓',
            '\\times': '×', '\\div': '÷', '\\cdot': '·',
            # 关系符号
            '\\neq': '≠', '\\leq': '≤', '\\geq': '≥', '\\approx': '≈',
            '\\equiv': '≡', '\\propto': '∝', '\\sim': '∼', '\\simeq': '≃',
            '\\ll': '≪', '\\gg': '≫', '\\subset': '⊂', '\\supset': '⊃',
            '\\subseteq': '⊆', '\\supseteq': '⊇', '\\in': '∈', '\\ni': '∋',
            # 箭头
            '\\rightarrow': '→', '\\leftarrow': '←', '\\Rightarrow': '⇒',
            '\\Leftarrow': '⇐', '\\leftrightarrow': '↔', '\\Leftrightarrow': '⇔',
            # 集合运算符
            '\\cup': '∪', '\\cap': '∩', '\\setminus': '∖',
            # 其他符号
            '\\forall': '∀', '\\exists': '∃', '\\emptyset': '∅', '\\angle': '∠',
            '\\triangle': '△', '\\parallel': '∥', '\\perp': '⊥'
        }
    
    def clean_formula(self, formula: str) -> str:
        """清理公式标记并转换 LaTeX 命令"""
        # 移除公式边界标记
        clean = re.sub(r'^\\\(|\\\)$|^\$|\$$|^\\\[|\\\]$', '', formula)
        
        # 应用 LaTeX 到 Unicode 的替换
        for latex, unicode_char in self.latex_to_unicode.items():
            clean = clean.replace(latex, unicode_char)
        
        # 清理多余的空白字符
        clean = re.sub(r'\s+', ' ', clean).strip()
        
        return clean
    
    def is_math_formula(self, text: str) -> bool:
        """判断是否为数学公式"""
        math_patterns = [r'^\\\(.*\\\)$', r'^\$.*\$$', r'^\\\[.*\\\]$']
        return any(re.match(pattern, text) for pattern in math_patterns)