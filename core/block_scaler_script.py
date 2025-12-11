# core/block_scaler_script.py
"""
通过调整 font-size 自适应容器高度的脚本（宽度由布局锁定）。
特别支持包含行内公式的混合文本块。
要求：必须在 MathJax / KaTeX 渲染完成且浏览器完成布局后触发缩放。
"""

BLOCK_SCALER_JS = '''
<script>
// ========== 状态管理 ==========
if (typeof window.formulasReady === "undefined") {
    window.formulasReady = false;
}

// ========== 防抖 ==========
function debounce(func, wait) {
    let timeout;
    return function() {
        clearTimeout(timeout);
        timeout = setTimeout(() => func.apply(this, arguments), wait);
    };
}

// ========== 主缩放函数：基于高度自适应 ==========
function scaleBlocksByFontSize() {
    console.log('🔤 开始字体缩放（基于高度适配，等待公式渲染完毕后执行）...');

    // 🔥 强制同步 reflow，确保所有动态内容（包括公式）已影响布局
    document.body.offsetHeight;

    // 选择需要缩放的 block：排除 .table, .image
    const blocks = document.querySelectorAll('div.block:not(.table):not(.image)');
    
    blocks.forEach((block, idx) => {
        const content = block.firstElementChild;
        if (!content) return;

        // 容器高度应作为参考上限（若为 0 则跳过）
        const containerHeight = block.clientHeight;
        if (containerHeight <= 10) return;

        // 允许通过 data-max-height 覆盖最大高度（单位 px）
        const maxHeightAttr = block.getAttribute('data-max-height');
        const targetMaxHeight = maxHeightAttr ? parseFloat(maxHeightAttr) : containerHeight;

        const originalFontSize = parseFloat(getComputedStyle(content).fontSize) || 16;
        const minFontSize = 1;
        const maxFontSize = 72;
        const tolerance = 0; // 高度误差容忍（px）
        const maxIter = 15;

        let fontSize = originalFontSize;
        let lastError = Infinity;
        let iter = 0;

        while (iter < maxIter) {
            content.style.fontSize = `${fontSize}px`;
            const currentHeight = block.scrollHeight;
            const error = currentHeight - targetMaxHeight;

            // 高度已满足要求（不超过目标 + 容差）
            if (error <= tolerance) break;

            // 如果高度不再改善（震荡或发散），退出
            if (error >= lastError) break;

            lastError = error;
            fontSize *= targetMaxHeight / currentHeight;
            fontSize = Math.max(minFontSize, Math.min(maxFontSize, fontSize));
            iter++;
        }

        // 清理 transform（兼容旧逻辑）
        content.style.transform = '';
        content.style.transformOrigin = '';

        console.log(`✅ 块 ${idx}: 最终字号=${fontSize.toFixed(2)}px, 高=${block.scrollHeight}px, 目标≤${targetMaxHeight}px`);
    });

    console.log('🎯 字体缩放（高度适配）完成');
}

// ========== 安全调度器：只有 formulasReady 为 true 时才执行 ==========
let pendingScale = false;
function scheduleScale() {
    if (pendingScale) return;
    pendingScale = true;

    const tryScale = () => {
        if (window.formulasReady) {
            pendingScale = false;
            scaleBlocksByFontSize();
        } else {
            // 继续等待
            setTimeout(tryScale, 50);
        }
    };
    tryScale();
}

// ========== 触发时机 ==========
document.addEventListener('DOMContentLoaded', scheduleScale);
window.addEventListener('load', () => setTimeout(scheduleScale, 100));
window.addEventListener('resize', debounce(scheduleScale, 100));

// 动态内容监听
if (typeof MutationObserver !== 'undefined') {
    const obs = new MutationObserver(() => {
        scheduleScale();
    });
    obs.observe(document.body, { childList: true, subtree: true });
}

// 保险：3秒后强制设为 ready（适用于无公式页面）
setTimeout(() => {
    if (!window.formulasReady) {
        console.warn('⚠️ 3秒未检测到公式渲染完成，假设无公式，继续缩放');
        window.formulasReady = true;
    }
}, 3000);
</script>
'''

def get_block_scaler_script() -> str:
    """
    返回用于按高度自适应缩放普通 block 元素的 JavaScript 脚本。
    排除 .table 和 .image 类型。
    支持通过 data-max-height="XXX" 指定每个 block 的最大允许高度（单位 px）。
    否则默认使用 block 自身 clientHeight 作为上限。
    """
    return BLOCK_SCALER_JS