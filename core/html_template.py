# core/html_template.py
"""
负责生成最终 HTML 页面的模板系统。
"""

from .mathjax_config import generate_mathjax_config
from .table_scaler_script import get_table_scaler_script
from .block_scaler_script import get_block_scaler_script


def generate_full_html(
    body_content: str,
    css_content: str,
    title: str = "Document Render",
    mathjax_config: dict = None,
    mathjax_debug: bool = False,
):
    mj_config_js = generate_mathjax_config(custom_config=mathjax_config, debug=mathjax_debug)
    table_script = get_table_scaler_script()
    block_script = get_block_scaler_script()

    # 🔥 修复版：确保 MathJax 渲染 + 布局稳定后再触发布局缩放
    mathjax_ready_script = """
<script>
(function() {
    function markFormulasReady() {
        // 强制同步 reflow，确保所有公式已完全融入文本流并影响布局
        document.body.offsetHeight;
        window.formulasReady = true;
        console.log('✅ 公式渲染与布局完成，触发布局缩放');
    }

    if (typeof MathJax !== 'undefined') {
        const waitForMathJax = () => {
            if (window.MathJax && MathJax.startup && MathJax.typesetPromise) {
                MathJax.startup.promise.then(() => {
                    return MathJax.typesetPromise();
                }).then(() => {
                    // 关键：延迟一小段时间 + 强制 reflow，应对异步字体/布局
                    setTimeout(markFormulasReady, 50);
                }).catch(err => {
                    console.error('MathJax 渲染出错:', err);
                    markFormulasReady(); // 即使失败也继续
                });
            } else {
                // MathJax 存在但未初始化（如无公式），稍等后就绪
                setTimeout(markFormulasReady, 300);
            }
        };

        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', waitForMathJax);
        } else {
            waitForMathJax();
        }
    } else {
        // 完全没有引入 MathJax（纯文本页面）
        markFormulasReady();
    }
})();
</script>
"""

    return f"""<!DOCTYPE html>
<html lang="zh">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <style>{css_content}</style>
  
  <!-- MathJax 配置 -->
  <script>
    MathJax = {mj_config_js};
  </script>
  <script src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-chtml.js" id="MathJax-script" async></script>
  
  {mathjax_ready_script}
</head>
<body>
  {body_content}
  {table_script}
  {block_script}
</body>
</html>"""