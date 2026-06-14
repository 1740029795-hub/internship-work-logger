/**
 * 实习工作记录器 — 日历视图交互 v2
 */

function Calendar(year, month, startOfWeek) {
    this.year = year;
    this.month = month;
    this.startOfWeek = startOfWeek || 0;
    this.today = new Date();
    this.todayStr = this.today.getFullYear() + '-' +
                    String(this.today.getMonth() + 1).padStart(2, '0') + '-' +
                    String(this.today.getDate()).padStart(2, '0');
    this.monthData = {};
    this.selectedDate = null;

    this.weekdayNames = this.startOfWeek === 0
        ? ['一', '二', '三', '四', '五', '六', '日']
        : ['日', '一', '二', '三', '四', '五', '六'];

    this.moods = ['', '😫', '😐', '😊', '😄', '🤩'];
}

Calendar.prototype.fetchMonthData = function() {
    var self = this;
    return fetch('/api/daily/month/' + this.year + '/' + this.month)
        .then(function(r) { return r.json(); })
        .then(function(data) {
            self.monthData = {};
            data.forEach(function(entry) {
                self.monthData[entry.entry_date] = entry;
            });
        })
        .catch(function(err) {
            console.error('Failed to fetch month data:', err);
        });
};

Calendar.prototype.render = function() {
    var self = this;
    showLoading('加载日历数据...');
    this.fetchMonthData().then(function() {
        hideLoading();
        self._renderGrid();
        self._updateHeader();
    });
};

Calendar.prototype._renderGrid = function() {
    var grid = this.getCalendarGrid();
    var container = document.getElementById('calendar-grid');
    var html = '';

    // 表头
    for (var i = 0; i < 7; i++) {
        var isWeekend = (this.startOfWeek === 0 && i >= 5) || (this.startOfWeek === 6 && i === 0);
        html += '<div class="calendar-header' + (isWeekend ? ' weekend' : '') + '">' +
                this.weekdayNames[i] + '</div>';
    }

    // 日期格子
    for (var row = 0; row < grid.length; row++) {
        for (var col = 0; col < grid[row].length; col++) {
            var cell = grid[row][col];
            var cls = 'calendar-cell';
            if (!cell.isCurrentMonth) cls += ' other-month';
            if (cell.isToday) cls += ' today';

            var moodHtml = '';
            if (cell.entry && cell.entry.mood) {
                moodHtml = '<span class="day-mood">' + (this.moods[cell.entry.mood] || '') + '</span>';
            }

            var dotsHtml = '';
            if (cell.entry) {
                var dotClass = cell.entry.is_workday ? 'workday' : 'rest';
                dotsHtml = '<div class="day-dot-row"><span class="day-dot ' + dotClass + '"></span></div>';
            }

            var previewHtml = '';
            if (cell.entry) {
                var t = cell.entry.title || cell.entry.content || '';
                if (t.length > 15) t = t.substring(0, 15) + '...';
                previewHtml = '<div class="day-preview">' + (t || '（无标题）') + '</div>';
            }

            var hoursHtml = '';
            if (cell.entry && cell.entry.work_hours) {
                hoursHtml = '<div class="day-hours">⏱ ' + cell.entry.work_hours + 'h</div>';
            }

            html += '<div class="' + cls + '" data-date="' + cell.date + '">' +
                    '<div class="day-number">' +
                        '<span>' + cell.day + '</span>' +
                        moodHtml +
                    '</div>' +
                    dotsHtml +
                    previewHtml +
                    hoursHtml +
                    '</div>';
        }
    }

    container.innerHTML = html;
    this._bindClickEvents();
    this._updateStats();
};

Calendar.prototype._bindClickEvents = function() {
    var self = this;
    var cells = document.querySelectorAll('.calendar-cell');
    cells.forEach(function(cell) {
        cell.addEventListener('click', function() {
            var dateStr = this.getAttribute('data-date');
            if (!dateStr) return;
            self._selectDate(dateStr);
        });
    });
};

Calendar.prototype._selectDate = function(dateStr) {
    this.selectedDate = dateStr;
    var entry = this.monthData[dateStr];
    var infoDiv = document.getElementById('selected-info');
    var dateEl = document.getElementById('sel-date');
    var summaryEl = document.getElementById('sel-summary');
    var editBtn = document.getElementById('sel-edit-btn');
    var createBtn = document.getElementById('sel-create-btn');

    infoDiv.style.display = 'block';
    dateEl.textContent = dateStr;

    if (entry) {
        var moods = ['', '😫', '😐', '😊', '😄', '🤩'];
        var moodIcon = moods[entry.mood] || '';
        summaryEl.textContent = (entry.title || '无标题') + ' · ' +
                               (entry.work_hours || 0) + 'h ' + moodIcon;
        editBtn.style.display = 'inline-block';
        createBtn.style.display = 'none';
    } else {
        summaryEl.textContent = '暂无日报记录';
        editBtn.style.display = 'none';
        createBtn.style.display = 'inline-block';
    }

    // 动态更新链接
    if (entry) {
        editBtn.href = '/daily/' + dateStr + '/edit';
    }
    createBtn.href = '/daily/create?date=' + dateStr;

    // 高亮
    document.querySelectorAll('.calendar-cell').forEach(function(c) {
        c.style.outline = 'none';
    });
    var target = document.querySelector('.calendar-cell[data-date="' + dateStr + '"]');
    if (target) target.style.outline = '2px solid var(--accent)';
};

Calendar.prototype._updateHeader = function() {
    document.getElementById('cal-title').textContent = this.year + '年 ' + this.month + '月';
};

Calendar.prototype._updateStats = function() {
    var data = this.monthData;
    var keys = Object.keys(data);
    var workdays = keys.filter(function(k) { return data[k].is_workday; }).length;
    var totalHours = 0;
    keys.forEach(function(k) {
        totalHours += (data[k].work_hours || 0);
    });
    totalHours = Math.round(totalHours * 10) / 10;

    var statsDiv = document.getElementById('calendar-stats');
    if (statsDiv) {
        statsDiv.innerHTML = '<span>📝 记录 ' + keys.length + ' 天</span>' +
                             '<span>💼 工作 ' + workdays + ' 天</span>' +
                             '<span>⏱ 共 ' + totalHours + ' 小时</span>';
    }
};

Calendar.prototype.getCalendarGrid = function() {
    var firstDay = new Date(this.year, this.month - 1, 1);
    var startDate = new Date(firstDay);
    var dayOfWeek = startDate.getDay();
    var offset = dayOfWeek - this.startOfWeek;
    if (offset < 0) offset += 7;
    startDate.setDate(startDate.getDate() - offset);

    var grid = [];
    for (var row = 0; row < 6; row++) {
        var week = [];
        for (var col = 0; col < 7; col++) {
            var d = new Date(startDate);
            d.setDate(d.getDate() + row * 7 + col);
            var dateStr = d.getFullYear() + '-' +
                         String(d.getMonth() + 1).padStart(2, '0') + '-' +
                         String(d.getDate()).padStart(2, '0');

            week.push({
                date: dateStr,
                day: d.getDate(),
                isCurrentMonth: d.getMonth() + 1 === this.month,
                isToday: dateStr === this.todayStr,
                entry: this.monthData[dateStr] || null
            });
        }
        grid.push(week);

        if (row >= 3) {
            var allNextMonth = week.every(function(d) { return !d.isCurrentMonth; });
            if (allNextMonth) break;
        }
    }
    return grid;
};

// ============================================================
// 月份导航
// ============================================================
document.addEventListener('DOMContentLoaded', function() {
    var currentYear = window.cal ? window.cal.year : new Date().getFullYear();
    var currentMonth = window.cal ? window.cal.month : new Date().getMonth() + 1;
    var startOfWeek = window.cal ? window.cal.startOfWeek : 0;

    function navigateMonth(y, m) {
        currentYear = y;
        currentMonth = m;
        window.cal = new Calendar(y, m, startOfWeek);
        window.cal.render();
        if (window.history && window.history.pushState) {
            window.history.pushState({}, '', '/daily/calendar?year=' + y + '&month=' + m);
        }
    }

    document.getElementById('btn-prev').addEventListener('click', function() {
        if (currentMonth === 1) { currentYear--; currentMonth = 12; }
        else { currentMonth--; }
        navigateMonth(currentYear, currentMonth);
    });

    document.getElementById('btn-next').addEventListener('click', function() {
        if (currentMonth === 12) { currentYear++; currentMonth = 1; }
        else { currentMonth++; }
        navigateMonth(currentYear, currentMonth);
    });

    document.getElementById('btn-today').addEventListener('click', function() {
        var today = new Date();
        navigateMonth(today.getFullYear(), today.getMonth() + 1);
    });

    // 键盘左右箭头切换月份
    document.addEventListener('keydown', function(e) {
        if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
        if (e.key === 'ArrowLeft') {
            e.preventDefault();
            document.getElementById('btn-prev').click();
        } else if (e.key === 'ArrowRight') {
            e.preventDefault();
            document.getElementById('btn-next').click();
        }
    });
});
