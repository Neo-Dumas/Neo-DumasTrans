# core/mathjax_config.py
"""
生成 MathJax 配置的 JS 对象字面量。
"""

import json
from typing import Dict, Any, Optional


def generate_mathjax_config(
    custom_config: Optional[Dict[str, Any]] = None,
    debug: bool = False
) -> str:
    """
    生成最终的 MathJax 配置 JS 对象字符串。

    Args:
        custom_config: 用户自定义配置，会覆盖默认值
        debug: 是否开启调试模式

    Returns:
        JSON 格式的 JS 对象字符串（可用于 <script> 中赋值给 MathJax）
    """
    default_config = {
        "tex": {
            "inlineMath": [['\\(', '\\)'], ['$', '$']],
            "displayMath": [['$$', '$$'], ['\\[', '\\]']],
            "processEscapes": True,
            "processEnvironments": True,
            "processRefs": True
        },
        "chtml": {
            "scale": 1.0,
            "minScale": 0.5,
            "matchFontHeight": True,
            "linebreaks": {
                "automatic": True,
                "width": "container"
            },
            "debug": debug
        },
        "options": {
            "skipHtmlTags": ['script', 'noscript', 'style', 'textarea', 'pre', 'code'],
            "ignoreHtmlClass": 'tex2jax_ignore'
        }
    }

    # 合并配置
    final_config = {**default_config}
    if custom_config:
        for key, value in custom_config.items():
            final_config[key] = value

    return json.dumps(final_config, ensure_ascii=False, separators=(',', ':'))