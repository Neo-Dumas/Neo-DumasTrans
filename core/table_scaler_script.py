# core/table_scaler_script.py
"""
生成用于自动缩放表格以适应容器的 JavaScript 脚本。
"""

TABLE_SCALER_JS = '''
<script>
function scaleTablesToFit() {
    console.log('🔧 开始表格缩放处理...');
    
    const tableBlocks = document.querySelectorAll('.block.table');
    console.log(`📊 找到 ${tableBlocks.length} 个表格块`);
    
    tableBlocks.forEach((block, index) => {
        try {
            const container = block.querySelector('div[style*="display:flex"]');
            if (!container) {
                console.log(`❌ 表格 ${index}: 找不到内层容器`);
                return;
            }
            
            const table = container.querySelector('table');
            if (!table) {
                console.log(`❌ 表格 ${index}: 找不到table元素`);
                return;
            }
            
            const containerWidth = container.clientWidth;
            const containerHeight = container.clientHeight;
            const tableWidth = table.scrollWidth;
            const tableHeight = table.scrollHeight;
            
            console.log(`表格 ${index}: 容器=${containerWidth}x${containerHeight}px, 表格=${tableWidth}x${tableHeight}px`);
            
            if (tableWidth <= 0 || tableHeight <= 0) {
                console.log(`⚠️ 表格 ${index}: 表格尺寸为0，跳过`);
                return;
            }
            
            const scaleX = containerWidth / tableWidth;
            const scaleY = containerHeight / tableHeight;

            let scale;
            if (tableWidth <= containerWidth && tableHeight <= containerHeight) {
                scale = Math.min(scaleX, scaleY);
                console.log(`表格 ${index}: 表格较小，采用保守缩放 X=${scaleX.toFixed(2)}, Y=${scaleY.toFixed(2)}`);
            } else {
                scale = Math.max(scaleX, scaleY);
                console.log(`表格 ${index}: 表格较大，采用激进缩放 X=${scaleX.toFixed(2)}, Y=${scaleY.toFixed(2)}`);
            }

            const safeScale = Math.max(0.01, Math.min(100.0, scale));
            
            console.log(`表格 ${index}: 最终缩放比例=${safeScale.toFixed(2)}倍`);
            table.style.transform = `scale(${safeScale})`;
            table.style.transformOrigin = 'center center';

            // === 二次缩放检查 ===
            setTimeout(() => {
                const scaledTableWidth = table.scrollWidth * safeScale;
                const scaledTableHeight = table.scrollHeight * safeScale;
                
                console.log(`表格 ${index}: 一次缩放后尺寸=${scaledTableWidth.toFixed(1)}x${scaledTableHeight.toFixed(1)}px`);
                
                if (scaledTableWidth > containerWidth * 1.05 || scaledTableHeight > containerHeight * 1.05) {
                    console.log(`🔄 表格 ${index}: 一次缩放后仍超出容器，进行二次缩放`);
                    
                    const secondScaleX = containerWidth / scaledTableWidth;
                    const secondScaleY = containerHeight / scaledTableHeight;
                    const secondScale = Math.min(secondScaleX, secondScaleY, 1.0);
                    const finalScale = safeScale * secondScale;
                    const safeFinalScale = Math.max(0.01, Math.min(100.0, finalScale));
                    
                    table.style.transform = `scale(${safeFinalScale})`;
                    console.log(`✅ 表格 ${index}: 二次缩放比例=${secondScale.toFixed(2)}, 最终=${safeFinalScale.toFixed(2)}倍`);
                    
                    // === 三次保险缩放 ===
                    setTimeout(() => {
                        const finalTableWidth = table.scrollWidth * safeFinalScale;
                        const finalTableHeight = table.scrollHeight * safeFinalScale;
                        
                        if (finalTableWidth > containerWidth * 1.1 || finalTableHeight > containerHeight * 1.1) {
                            console.log(`⚠️ 表格 ${index}: 二次缩放后仍不理想，应用强制缩放`);
                            
                            const forceScaleX = containerWidth / finalTableWidth;
                            const forceScaleY = containerHeight / finalTableHeight;
                            const forceScale = Math.min(forceScaleX, forceScaleY, 1.0);
                            const ultimateScale = safeFinalScale * forceScale;
                            
                            table.style.transform = `scale(${ultimateScale})`;
                            console.log(`🛠️ 表格 ${index}: 强制缩放比例=${forceScale.toFixed(2)}, 最终=${ultimateScale.toFixed(2)}倍`);
                        }
                    }, 50);
                }
            }, 50);

        } catch (error) {
            console.error(`❌ 表格 ${index} 处理失败:`, error);
        }
    });
    
    console.log('🎯 表格缩放处理完成');
}

// 多时机触发
document.addEventListener('DOMContentLoaded', () => {
    console.log('📄 DOM内容加载完成，开始表格缩放');
    scaleTablesToFit();
});

window.addEventListener('load', () => {
    console.log('🖼️ 页面完全加载（包括图片），重新缩放表格');
    setTimeout(scaleTablesToFit, 100);
});

window.addEventListener('resize', () => {
    console.log('🔄 窗口大小变化，重新缩放表格');
    setTimeout(scaleTablesToFit, 50);
});

// 动态内容监听
if (typeof MutationObserver !== 'undefined') {
    const observer = new MutationObserver(mutations => {
        let shouldRescale = false;
        mutations.forEach(mutation => {
            if (mutation.type === 'childList') {
                mutation.addedNodes.forEach(node => {
                    if (node.nodeType === 1 && (node.querySelector?.('table') || node.classList?.contains?.('block'))) {
                        shouldRescale = true;
                    }
                });
            }
        });
        if (shouldRescale) {
            console.log('🔄 检测到DOM变化，重新缩放表格');
            setTimeout(scaleTablesToFit, 100);
        }
    });
    
    observer.observe(document.body, { childList: true, subtree: true });
}

// 保险机制：3秒后再执行一次
setTimeout(scaleTablesToFit, 3000);
</script>
'''

# 可暴露为函数或直接导出常量
def get_table_scaler_script() -> str:
    return TABLE_SCALER_JS