# core/html_template.py
"""
负责生成最终 HTML 页面的模板系统。
"""

from .mathjax_config import generate_mathjax_config
from .table_scaler_script import get_table_scaler_script
from .block_scaler_script import get_block_scaler_script  # 新增导入

def generate_full_html(
    body_content: str,
    css_content: str,
    title: str = "Document Render",
    mathjax_config: dict = None,
    mathjax_debug: bool = False,
):
    mj_config_js = generate_mathjax_config(custom_config=mathjax_config, debug=mathjax_debug)
    table_script = get_table_scaler_script()
    block_script = get_block_scaler_script()  # 新增

    return f"""<!DOCTYPE html>
<html lang="zh">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <style>{css_content}</style>
  
  <script>
    MathJax = {mj_config_js};
  </script>
  <script src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-chtml.js" async></script>

  <script>
    // ... MathJax 监听代码 ...
  </script>
</head>
<body>
  {body_content}
  {table_script}
  {block_script}  <!-- 插入新脚本 -->
</body>
</html>"""