# core/table_scaler_script.py
"""
生成用于自动缩放表格以适应容器高度的 JavaScript 脚本。
- 首先按原逻辑仅基于高度缩放（确保高度 ≤ 容器）
- 然后检查宽度：若表格宽度 > 容器宽度，则额外缩放一次以适配宽度
- 宽度修正仅执行一次，且不会破坏高度约束
- 要求：在 MathJax / KaTeX 渲染完成且布局稳定后执行
"""

TABLE_SCALER_JS = '''
<script>
// ========== 状态管理（与文字块脚本共享）==========
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

// ========== 表格高度优先 + 宽度兜底缩放 ==========
function scaleTablesByFontSize() {
    console.log('🔤 开始表格字号缩放（高度优先，宽度兜底）...');

    // 🔥 强制 reflow，确保公式和布局已稳定
    document.body.offsetHeight;

    const tableBlocks = document.querySelectorAll('.block.table');
    
    tableBlocks.forEach((block, idx) => {
        const container = block.querySelector('div[style*="display:flex"]');
        if (!container) return;

        const table = container.querySelector('table');
        if (!table) return;

        const containerHeight = container.clientHeight;
        const containerWidth = container.clientWidth;
        if (containerHeight <= 10 || containerWidth <= 10) return;

        const maxHeightAttr = block.getAttribute('data-max-height');
        const targetMaxHeight = maxHeightAttr ? parseFloat(maxHeightAttr) : containerHeight;

        const originalFontSize = parseFloat(getComputedStyle(table).fontSize) || 14;
        const minFontSize = 1;
        const maxFontSize = 72;
        const tolerance = 0; // 高度误差容忍（px）
        const maxIter = 15;

        let fontSize = originalFontSize;
        let lastError = Infinity;
        let iter = 0;

        // ========== 第一阶段：仅基于高度缩放（原逻辑） ==========
        while (iter < maxIter) {
            table.style.fontSize = `${fontSize}px`;
            const currentHeight = table.scrollHeight;
            const error = currentHeight - targetMaxHeight;

            if (error <= tolerance) {
                break;
            }

            if (error >= lastError) {
                break;
            }

            lastError = error;
            fontSize *= targetMaxHeight / currentHeight;
            fontSize = Math.max(minFontSize, Math.min(maxFontSize, fontSize));
            iter++;
        }

        // ========== 第二阶段：检查宽度，若超宽则兜底缩放一次 ==========
        const finalWidth = table.scrollWidth;
        if (finalWidth > containerWidth + tolerance) {
            const widthScale = containerWidth / finalWidth;
            const newFontSize = fontSize * widthScale;
            fontSize = Math.max(minFontSize, newFontSize);
            table.style.fontSize = `${fontSize}px`;
            console.log(`📏 表格 ${idx}: 宽度超标（${finalWidth}px > ${containerWidth}px），应用宽度兜底缩放`);
        }

        // 清理 transform（兼容旧版）
        table.style.transform = '';
        table.style.transformOrigin = '';

        const finalHeight = table.scrollHeight;
        const finalW = table.scrollWidth;
        console.log(
            `✅ 表格 ${idx}: 最终字号=${fontSize.toFixed(2)}px, 尺寸=${finalW}×${finalHeight}px, ` +
            `容器=${containerWidth}×${targetMaxHeight}px`
        );
    });

    console.log('🎯 表格字号缩放（高度优先 + 宽度兜底）完成');
}

// ========== 安全调度器（与文字块脚本一致）==========
let pendingTableScale = false;
function scheduleTableScale() {
    if (pendingTableScale) return;
    pendingTableScale = true;

    const tryScale = () => {
        if (window.formulasReady) {
            pendingTableScale = false;
            scaleTablesByFontSize();
        } else {
            setTimeout(tryScale, 50);
        }
    };
    tryScale();
}

// ========== 触发时机（完全对齐文字块）==========
document.addEventListener('DOMContentLoaded', scheduleTableScale);
window.addEventListener('load', () => setTimeout(scheduleTableScale, 100));
window.addEventListener('resize', debounce(scheduleTableScale, 100));

if (typeof MutationObserver !== 'undefined') {
    const obs = new MutationObserver(() => {
        scheduleTableScale();
    });
    obs.observe(document.body, { childList: true, subtree: true });
}

// 保险：3秒后强制设为 ready
setTimeout(() => {
    if (!window.formulasReady) {
        console.warn('⚠️ 3秒未检测到公式渲染完成，假设无公式，继续表格缩放');
        window.formulasReady = true;
    }
}, 3000);
</script>
'''

def get_table_scaler_script() -> str:
    """
    返回用于表格缩放的 JavaScript 脚本。
    - 首先通过 font-size 调整使表格高度 ≤ 容器高度（或 data-max-height）
    - 然后检查宽度，若超出容器宽度，则额外缩放一次以适配宽度
    - 确保最终表格完全容纳于容器内
    """
    return TABLE_SCALER_JS