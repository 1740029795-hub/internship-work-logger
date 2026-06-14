/**
 * 实习工作记录器 — 通用 JavaScript v2
 * 包含: Toast, 弹窗, 标签输入, 加载遮罩, 快捷键
 */

// ============================================================
// Toast 自动消失
// ============================================================
document.addEventListener('DOMContentLoaded', function() {
    document.querySelectorAll('.toast[data-auto-dismiss]').forEach(function(t) {
        setTimeout(function() {
            t.style.animation = 'slideOut 0.3s ease forwards';
            setTimeout(function() { t.remove(); }, 300);
        }, 3500);
    });
});

// ============================================================
// 自定义确认弹窗 (替代浏览器 confirm)
// ============================================================
function showConfirm(message, title, icon) {
    title = title || '确认操作';
    icon = icon || '⚠️';
    message = message || '确定要执行此操作吗？';

    return new Promise(function(resolve) {
        var overlay = document.getElementById('confirm-modal');
        document.getElementById('confirm-title').textContent = title;
        document.getElementById('confirm-message').textContent = message;
        overlay.querySelector('.modal-icon').textContent = icon;
        overlay.style.display = 'flex';

        function cleanup() {
            overlay.style.display = 'none';
            document.getElementById('confirm-ok').removeEventListener('click', onOk);
            document.getElementById('confirm-cancel').removeEventListener('click', onCancel);
        }

        function onOk() { cleanup(); resolve(true); }
        function onCancel() { cleanup(); resolve(false); }

        document.getElementById('confirm-ok').addEventListener('click', onOk);
        document.getElementById('confirm-cancel').addEventListener('click', onCancel);

        // ESC 关闭
        function onKey(e) {
            if (e.key === 'Escape') { cleanup(); document.removeEventListener('keydown', onKey); resolve(false); }
        }
        document.addEventListener('keydown', onKey);
    });
}

// 兼容旧的 confirmDelete 函数
async function confirmDelete(url, message) {
    var ok = await showConfirm(message || '确定要删除吗？此操作不可撤销。', '删除确认', '🗑️');
    if (ok) {
        var form = document.createElement('form');
        form.method = 'POST';
        form.action = url;
        document.body.appendChild(form);
        form.submit();
    }
}

// ============================================================
// 加载遮罩
// ============================================================
function showLoading(text) {
    text = text || '处理中...';
    document.getElementById('loading-text').textContent = text;
    document.getElementById('loading-overlay').style.display = 'flex';
}

function hideLoading() {
    document.getElementById('loading-overlay').style.display = 'none';
}

// 为所有 form 自动绑定加载状态 (生成报告等操作)
document.addEventListener('DOMContentLoaded', function() {
    var generateForms = document.querySelectorAll('form[action*="generate"]');
    generateForms.forEach(function(form) {
        form.addEventListener('submit', function() {
            var type = '';
            if (form.action.indexOf('weekly') >= 0) type = '正在生成周报...';
            else if (form.action.indexOf('monthly') >= 0) type = '正在生成月报...';
            else if (form.action.indexOf('annual') >= 0) type = '正在生成年报...';
            else type = '处理中...';
            showLoading(type);
        });
    });

    // 为导出链接绑定加载状态
    var exportLinks = document.querySelectorAll('a[href*="/export/"]');
    exportLinks.forEach(function(link) {
        link.addEventListener('click', function() {
            showLoading('正在导出文件...');
            // 延迟隐藏（导出通常会下载文件，页面不刷新）
            setTimeout(hideLoading, 3000);
        });
    });
});

// ============================================================
// 心情选择器
// ============================================================
function initMoodSelector() {
    var options = document.querySelectorAll('.mood-option');
    var hiddenInput = document.getElementById('mood-input');
    if (!options.length) return;

    options.forEach(function(opt) {
        opt.addEventListener('click', function() {
            options.forEach(function(o) { o.classList.remove('selected'); });
            opt.classList.add('selected');
            if (hiddenInput) hiddenInput.value = opt.getAttribute('data-value');
        });
    });
}

// ============================================================
// 标签输入组件
// ============================================================
function initTagInput() {
    var wrapper = document.querySelector('.tag-input-wrapper');
    if (!wrapper) return;

    var hiddenInput = document.getElementById('tags-hidden');
    var realInput = wrapper.querySelector('.tag-input-real');
    var chips = [];

    function loadChips() {
        if (!hiddenInput) return;
        var tags = hiddenInput.value.split(',').filter(function(t) { return t.trim(); });
        tags.forEach(function(t) { addChip(t.trim()); });
    }

    function updateHidden() {
        if (!hiddenInput) return;
        hiddenInput.value = chips.join(', ');
    }

    function addChip(text) {
        if (!text || chips.indexOf(text) >= 0) return;
        chips.push(text);
        updateHidden();

        var chip = document.createElement('span');
        chip.className = 'tag-chip';
        chip.innerHTML = text + '<span class="tag-remove">&times;</span>';
        chip.querySelector('.tag-remove').addEventListener('click', function(e) {
            e.stopPropagation();
            chips = chips.filter(function(c) { return c !== text; });
            updateHidden();
            chip.remove();
        });
        wrapper.insertBefore(chip, realInput);
    }

    wrapper.addEventListener('click', function() { realInput.focus(); });

    realInput.addEventListener('keydown', function(e) {
        if (e.key === 'Enter' || e.key === ',') {
            e.preventDefault();
            var val = realInput.value.replace(/,/g, '').trim();
            if (val) { addChip(val); realInput.value = ''; }
        }
        if (e.key === 'Backspace' && realInput.value === '' && chips.length > 0) {
            var lastChip = chips[chips.length - 1];
            chips.pop();
            updateHidden();
            var allChips = wrapper.querySelectorAll('.tag-chip');
            if (allChips.length > 0) allChips[allChips.length - 1].remove();
        }
    });

    realInput.addEventListener('blur', function() {
        var val = realInput.value.replace(/,/g, '').trim();
        if (val) { addChip(val); realInput.value = ''; }
    });

    loadChips();
}

// ============================================================
// 自动保存草稿
// ============================================================
var autosaveTimer = null;

function autosaveDaily(formSelector, storageKey) {
    var form = document.querySelector(formSelector);
    if (!form) return;

    function save() {
        var data = {};
        var inputs = form.querySelectorAll('input, textarea, select');
        inputs.forEach(function(inp) {
            if (inp.name) data[inp.name] = inp.value;
        });
        var tagsHidden = document.getElementById('tags-hidden');
        if (tagsHidden) data['tags'] = tagsHidden.value;

        try {
            localStorage.setItem(storageKey, JSON.stringify(data));
        } catch(e) {}
    }

    function restore() {
        var saved = localStorage.getItem(storageKey);
        if (!saved) return;
        try {
            var data = JSON.parse(saved);
            Object.keys(data).forEach(function(key) {
                var el = form.querySelector('[name="' + key + '"]');
                if (el && el.type !== 'hidden') el.value = data[key];
                if (key === 'tags') {
                    var tagsHidden = document.getElementById('tags-hidden');
                    if (tagsHidden) tagsHidden.value = data[key];
                    // 重新加载标签chips
                    if (data[key]) {
                        var wrapper = document.querySelector('.tag-input-wrapper');
                        var chips = data[key].split(',').filter(function(t) { return t.trim(); });
                        chips.forEach(function(t) {
                            var text = t.trim();
                            if (!text) return;
                            var chip = document.createElement('span');
                            chip.className = 'tag-chip';
                            chip.innerHTML = text + '<span class="tag-remove">&times;</span>';
                            chip.querySelector('.tag-remove').addEventListener('click', function(ev) {
                                ev.stopPropagation();
                                chip.remove();
                            });
                            var realInput = wrapper.querySelector('.tag-input-real');
                            wrapper.insertBefore(chip, realInput);
                        });
                    }
                }
            });
        } catch(e) {}
    }

    restore();

    form.addEventListener('input', function() {
        clearTimeout(autosaveTimer);
        autosaveTimer = setTimeout(save, 2000);
    });

    form.addEventListener('submit', function() {
        localStorage.removeItem(storageKey);
    });
}

// ============================================================
// 全局快捷键
// ============================================================
document.addEventListener('keydown', function(e) {
    // 在输入框中不触发快捷键
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.tagName === 'SELECT') {
        return;
    }

    switch(e.key.toLowerCase()) {
        case 'n':
            // N = 写日报
            if (!e.ctrlKey && !e.metaKey && !e.altKey) {
                e.preventDefault();
                window.location.href = '/daily/create';
            }
            break;
        case 'd':
            // D = 仪表盘
            if (!e.ctrlKey && !e.metaKey && !e.altKey) {
                e.preventDefault();
                window.location.href = '/';
            }
            break;
        case 'l':
            // L = 日报列表
            if (!e.ctrlKey && !e.metaKey && !e.altKey) {
                e.preventDefault();
                window.location.href = '/daily/list';
            }
            break;
        case 'c':
            // C = 日历
            if (!e.ctrlKey && !e.metaKey && !e.altKey) {
                e.preventDefault();
                window.location.href = '/daily/calendar';
            }
            break;
        case 'w':
            // W = 周报
            if (!e.ctrlKey && !e.metaKey && !e.altKey) {
                e.preventDefault();
                window.location.href = '/report/weekly';
            }
            break;
        case 'm':
            // M = 月报
            if (!e.ctrlKey && !e.metaKey && !e.altKey) {
                e.preventDefault();
                window.location.href = '/report/monthly';
            }
            break;
    }
});

// ============================================================
// 初始化
// ============================================================
document.addEventListener('DOMContentLoaded', function() {
    initMoodSelector();
    initTagInput();
});
