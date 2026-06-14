/**
 * 实习工作记录器 — 报告页交互
 */

// 报告页的文本区域自适应高度
document.addEventListener('DOMContentLoaded', function() {
    var textareas = document.querySelectorAll('.report-sections textarea');
    textareas.forEach(function(ta) {
        function autoResize() {
            ta.style.height = 'auto';
            ta.style.height = Math.max(ta.scrollHeight, 80) + 'px';
        }
        ta.addEventListener('input', autoResize);
        // 初始调整
        autoResize();
    });
});
