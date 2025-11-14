# core/block_scaler_script.py
"""
生成用于自动缩放普通 block 元素以适应容器的 JavaScript 脚本。
仅处理非表格、非图片、非行间公式的 block。
"""

BLOCK_SCALER_JS = '''
<script>
function scaleBlocksToFit() {
    console.log('🔧 开始普通块级元素缩放处理...');
    
    // 匹配所有 block 但排除 table / image / interline_equation
    const blockElements = document.querySelectorAll('div.block:not(.table):not(.image):not(.interline_equation)');
    console.log(`📊 找到 ${blockElements.length} 个需缩放的普通块`);

    blockElements.forEach((block, index) => {
        try {
            // 假设 block 内部有一个主要的可缩放内容容器（如 div 或直接子元素）
            // 我们尝试获取其直接内容容器或第一个有意义的子元素
            const content = block.firstElementChild;
            if (!content) {
                console.log(`⚠️ 块 ${index}: 无子元素，跳过`);
                return;
            }

            const containerWidth = block.clientWidth;
            const containerHeight = block.clientHeight;
            const contentWidth = content.scrollWidth;
            const contentHeight = content.scrollHeight;

            console.log(`块 ${index}: 容器=${containerWidth}x${containerHeight}px, 内容=${contentWidth}x${contentHeight}px`);

            if (contentWidth <= 0 || contentHeight <= 0) {
                console.log(`⚠️ 块 ${index}: 内容尺寸为0，跳过`);
                return;
            }

            const scaleX = containerWidth / contentWidth;
            const scaleY = containerHeight / contentHeight;

            let scale;
            if (contentWidth <= containerWidth && contentHeight <= containerHeight) {
                // 内容较小：保守缩放（避免过度放大模糊）
                scale = Math.min(scaleX, scaleY);
                console.log(`块 ${index}: 内容较小，采用保守缩放 X=${scaleX.toFixed(2)}, Y=${scaleY.toFixed(2)}`);
            } else {
                // 内容过大：激进缩放以确保 fit
                scale = Math.max(scaleX, scaleY);
                console.log(`块 ${index}: 内容较大，采用激进缩放 X=${scaleX.toFixed(2)}, Y=${scaleY.toFixed(2)}`);
            }

            const safeScale = Math.max(0.01, Math.min(100.0, scale));
            console.log(`块 ${index}: 最终缩放比例=${safeScale.toFixed(2)}倍`);

            // 应用 transform 缩放
            content.style.transform = `scale(${safeScale})`;
            content.style.transformOrigin = '0 0';  // 保持左上对齐，避免偏移
            //content.style.display = 'inline-block';       // 确保 transform 生效
            content.style.width = 'auto';                 // 防止 width:100% 抵消缩放

            // === 二次缩放检查 ===
            setTimeout(() => {
                const scaledWidth = content.scrollWidth * safeScale;
                const scaledHeight = content.scrollHeight * safeScale;

                console.log(`块 ${index}: 一次缩放后尺寸=${scaledWidth.toFixed(1)}x${scaledHeight.toFixed(1)}px`);

                if (scaledWidth > containerWidth * 1.05 || scaledHeight > containerHeight * 1.05) {
                    console.log(`🔄 块 ${index}: 一次缩放后仍超出容器，进行二次缩放`);

                    const secondScaleX = containerWidth / scaledWidth;
                    const secondScaleY = containerHeight / scaledHeight;
                    const secondScale = Math.min(secondScaleX, secondScaleY, 1.0);
                    const finalScale = safeScale * secondScale;
                    const safeFinalScale = Math.max(0.01, Math.min(100.0, finalScale));

                    content.style.transform = `scale(${safeFinalScale})`;
                    console.log(`✅ 块 ${index}: 二次缩放比例=${secondScale.toFixed(2)}, 最终=${safeFinalScale.toFixed(2)}倍`);

                    // === 三次保险缩放 ===
                    setTimeout(() => {
                        const finalWidth = content.scrollWidth * safeFinalScale;
                        const finalHeight = content.scrollHeight * safeFinalScale;

                        if (finalWidth > containerWidth * 1.1 || finalHeight > containerHeight * 1.1) {
                            console.log(`⚠️ 块 ${index}: 二次缩放后仍不理想，应用强制缩放`);

                            const forceScaleX = containerWidth / finalWidth;
                            const forceScaleY = containerHeight / finalHeight;
                            const forceScale = Math.min(forceScaleX, forceScaleY, 1.0);
                            const ultimateScale = safeFinalScale * forceScale;

                            content.style.transform = `scale(${ultimateScale})`;
                            console.log(`🛠️ 块 ${index}: 强制缩放比例=${forceScale.toFixed(2)}, 最终=${ultimateScale.toFixed(2)}倍`);
                        }
                    }, 50);
                }
            }, 50);

        } catch (error) {
            console.error(`❌ 块 ${index} 处理失败:`, error);
        }
    });

    console.log('🎯 普通块级元素缩放处理完成');
}

// 多时机触发
document.addEventListener('DOMContentLoaded', () => {
    console.log('📄 DOM内容加载完成，开始普通块缩放');
    scaleBlocksToFit();
});

window.addEventListener('load', () => {
    console.log('🖼️ 页面完全加载（包括图片），重新缩放普通块');
    setTimeout(scaleBlocksToFit, 100);
});

window.addEventListener('resize', () => {
    console.log('🔄 窗口大小变化，重新缩放普通块');
    setTimeout(scaleBlocksToFit, 50);
});

// 动态内容监听
if (typeof MutationObserver !== 'undefined') {
    const observer = new MutationObserver(mutations => {
        let shouldRescale = false;
        mutations.forEach(mutation => {
            if (mutation.type === 'childList') {
                mutation.addedNodes.forEach(node => {
                    if (node.nodeType === 1) {
                        // 如果新增节点是 block 或包含 block，则标记需重缩放
                        if (node.matches?.('div.block') || node.querySelector?.('div.block:not(.table):not(.image):not(.interline_equation)')) {
                            shouldRescale = true;
                        }
                    }
                });
            }
        });
        if (shouldRescale) {
            console.log('🔄 检测到DOM变化，重新缩放普通块');
            setTimeout(scaleBlocksToFit, 100);
        }
    });

    observer.observe(document.body, { childList: true, subtree: true });
}

// 保险机制：3秒后再执行一次
setTimeout(scaleBlocksToFit, 3000);
</script>
'''

def get_block_scaler_script() -> str:
    """
    返回用于缩放普通 block 元素的 JavaScript 脚本。
    排除 .table, .image, .interline_equation 类型。
    """
    return BLOCK_SCALER_JS