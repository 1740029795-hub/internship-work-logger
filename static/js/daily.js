/**
 * 实习工作记录器 — 日报表单增强
 */

// 日报表单快捷键 (Ctrl+S 保存)
document.addEventListener('DOMContentLoaded', function() {
    var form = document.getElementById('daily-form');
    if (!form) return;

    // Ctrl+S 保存
    document.addEventListener('keydown', function(e) {
        if ((e.ctrlKey || e.metaKey) && e.key === 's') {
            e.preventDefault();
            form.submit();
        }
    });

    // 离开页面时提示（如果有未保存的更改）
    var dirty = false;
    var inputs = form.querySelectorAll('input, textarea');
    inputs.forEach(function(inp) {
        inp.addEventListener('input', function() { dirty = true; });
    });

    window.addEventListener('beforeunload', function(e) {
        if (dirty) {
            e.preventDefault();
            e.returnValue = '你有未保存的更改，确定要离开吗？';
            return e.returnValue;
        }
    });
});
