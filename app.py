"""
实习工作记录器 — Flask 主程序
"""
import os
import io
import re
import json
from datetime import datetime, date, timedelta

from flask import Flask, render_template, request, redirect, url_for, jsonify, Response, flash

from database import init_db, get_db, get_settings, save_settings
from calendar_utils import (
    parse_date, format_date, get_week_boundaries, get_month_boundaries,
    get_calendar_grid, get_internship_week_number, month_label,
    chinese_weekday, get_week_label, get_all_week_starts
)

app = Flask(__name__)
app.secret_key = 'internship-logger-secret-key-2026'

# 启动时初始化数据库
init_db()

# 确保 exports 和 backups 目录存在
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
EXPORTS_DIR = os.path.join(BASE_DIR, 'exports')
BACKUPS_DIR = os.path.join(BASE_DIR, 'backups')
os.makedirs(EXPORTS_DIR, exist_ok=True)
os.makedirs(BACKUPS_DIR, exist_ok=True)


# --- 上下文处理器：注入设置到所有模板 ---
@app.context_processor
def inject_settings():
    settings = get_settings()
    # 侧边栏今日状态
    today_str = format_date(date.today())
    conn = get_db()
    today_entry = conn.execute(
        'SELECT id, mood FROM daily_entries WHERE entry_date = ?', (today_str,)
    ).fetchone()
    conn.close()
    settings['_today_has_entry'] = today_entry is not None
    settings['_today_mood'] = today_entry['mood'] if today_entry else None
    return dict(app_settings=settings)


# --- 工具函数 ---
def _get_page_args():
    """获取分页参数"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    if page < 1:
        page = 1
    if per_page < 1:
        per_page = 20
    return page, per_page


def _calc_stats():
    """计算仪表盘统计数据"""
    conn = get_db()
    total = conn.execute('SELECT COUNT(*) FROM daily_entries WHERE is_workday=1').fetchone()[0]
    today = date.today()
    this_month = conn.execute(
        'SELECT COUNT(*) FROM daily_entries WHERE entry_date LIKE ? AND is_workday=1',
        (today.strftime('%Y-%m') + '%',)
    ).fetchone()[0]

    # 连续打卡天数
    streak = 0
    check_date = today
    while True:
        ds = format_date(check_date)
        row = conn.execute(
            'SELECT id FROM daily_entries WHERE entry_date = ? AND is_workday=1', (ds,)
        ).fetchone()
        if row:
            streak += 1
            check_date -= timedelta(days=1)
        else:
            # 如果今天是周末且没记录，不算断
            if check_date.weekday() >= 5:  # 周六日
                check_date -= timedelta(days=1)
                continue
            break

    # 本月总工时
    month_hours = conn.execute(
        'SELECT COALESCE(SUM(work_hours), 0) FROM daily_entries WHERE entry_date LIKE ?',
        (today.strftime('%Y-%m') + '%',)
    ).fetchone()[0]

    # 本周工时
    settings = get_settings()
    week_start_day = int(settings.get('weekly_start_day', 0))
    ws, we = get_week_boundaries(today, week_start_day)
    week_hours = conn.execute(
        'SELECT COALESCE(SUM(work_hours), 0) FROM daily_entries WHERE entry_date BETWEEN ? AND ?',
        (format_date(ws), format_date(we))
    ).fetchone()[0]

    conn.close()
    return total, this_month, streak, round(month_hours, 1), round(week_hours, 1)


# ============================================================
# 首页 / 仪表盘
# ============================================================
@app.route('/')
def index():
    settings = get_settings()
    total_dailies, workdays_this_month, streak, month_hours, week_hours = _calc_stats()

    # 实习天数计算
    days_elapsed = 0
    days_total = 0
    progress_pct = 0
    remaining_days = 0
    if settings.get('start_date') and settings.get('end_date'):
        start = parse_date(settings['start_date'])
        end = parse_date(settings['end_date'])
        today = date.today()
        days_total = (end - start).days + 1
        if today >= start:
            elapsed = (min(today, end) - start).days + 1
            days_elapsed = elapsed if elapsed > 0 else 0
        remaining_days = max(0, days_total - days_elapsed)
        if days_total > 0:
            progress_pct = min(round(days_elapsed / days_total * 100), 100)

    # 最近 5 条日报
    conn = get_db()
    recent = conn.execute(
        'SELECT * FROM daily_entries ORDER BY entry_date DESC LIMIT 5'
    ).fetchall()
    recent = [dict(r) for r in recent]

    # 本周概览
    today = date.today()
    week_start_day = int(settings.get('weekly_start_day', 0))
    week_start, week_end = get_week_boundaries(today, week_start_day)
    week_entries = conn.execute(
        'SELECT entry_date, is_workday, mood FROM daily_entries WHERE entry_date BETWEEN ? AND ?',
        (format_date(week_start), format_date(week_end))
    ).fetchall()
    week_map = {r['entry_date']: dict(r) for r in week_entries}
    conn.close()

    # 本周每天的状态
    week_days = []
    for i in range(7):
        d = week_start + timedelta(days=i)
        ds = format_date(d)
        entry = week_map.get(ds)
        week_days.append({
            'date': ds,
            'weekday': chinese_weekday(d.weekday()),
            'has_entry': entry is not None,
            'is_workday': entry['is_workday'] if entry else (d.weekday() < 5),
            'mood': entry['mood'] if entry else None,
            'is_today': d == today,
        })

    return render_template('index.html',
                           total_dailies=total_dailies,
                           workdays_this_month=workdays_this_month,
                           streak=streak,
                           month_hours=month_hours,
                           week_hours=week_hours,
                           days_elapsed=days_elapsed,
                           days_total=days_total,
                           progress_pct=progress_pct,
                           remaining_days=remaining_days,
                           recent=recent,
                           week_days=week_days,
                           today=format_date(today))


# ============================================================
# 设置页
# ============================================================
@app.route('/settings', methods=['GET', 'POST'])
def settings_page():
    if request.method == 'POST':
        save_settings(request.form)
        flash('设置已保存', 'success')
        return redirect(url_for('settings_page'))

    settings = get_settings()
    return render_template('settings.html', settings=settings)


# ============================================================
# 日报 CRUD
# ============================================================
@app.route('/daily/create', methods=['GET', 'POST'])
def daily_create():
    prefilled_date = request.args.get('date', format_date(date.today()))

    if request.method == 'POST':
        entry_date = request.form.get('entry_date', prefilled_date)
        data = {
            'entry_date': entry_date,
            'title': request.form.get('title', ''),
            'content': request.form.get('content', ''),
            'work_hours': float(request.form.get('work_hours', 8)),
            'tasks_completed': request.form.get('tasks_completed', ''),
            'tasks_planned': request.form.get('tasks_planned', ''),
            'challenges': request.form.get('challenges', ''),
            'learnings': request.form.get('learnings', ''),
            'tags': request.form.get('tags', ''),
            'mood': int(request.form.get('mood', 3)),
            'is_workday': 1 if request.form.get('is_workday') else 0,
        }

        conn = get_db()
        try:
            conn.execute('''
                INSERT OR REPLACE INTO daily_entries
                (entry_date, title, content, work_hours, tasks_completed, tasks_planned,
                 challenges, learnings, tags, mood, is_workday, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now','localtime'))
            ''', (data['entry_date'], data['title'], data['content'], data['work_hours'],
                  data['tasks_completed'], data['tasks_planned'], data['challenges'],
                  data['learnings'], data['tags'], data['mood'], data['is_workday']))
            conn.commit()
            flash(f'{entry_date} 日报已保存', 'success')
        except Exception as e:
            conn.rollback()
            conn.close()
            flash(f'保存失败：{e}', 'error')
            return render_template('daily_create.html', entry=data, prefilled_date=prefilled_date)
        conn.close()
        return redirect(url_for('daily_list'))

    return render_template('daily_create.html', entry=None, prefilled_date=prefilled_date)


@app.route('/daily/<date_str>/edit', methods=['GET', 'POST'])
def daily_edit(date_str):
    conn = get_db()
    row = conn.execute('SELECT * FROM daily_entries WHERE entry_date = ?', (date_str,)).fetchone()

    if not row:
        conn.close()
        flash('该日期暂无日报，请先创建', 'error')
        return redirect(url_for('daily_create', date=date_str))

    entry = dict(row)

    if request.method == 'POST':
        data = {
            'entry_date': date_str,
            'title': request.form.get('title', ''),
            'content': request.form.get('content', ''),
            'work_hours': float(request.form.get('work_hours', 8)),
            'tasks_completed': request.form.get('tasks_completed', ''),
            'tasks_planned': request.form.get('tasks_planned', ''),
            'challenges': request.form.get('challenges', ''),
            'learnings': request.form.get('learnings', ''),
            'tags': request.form.get('tags', ''),
            'mood': int(request.form.get('mood', 3)),
            'is_workday': 1 if request.form.get('is_workday') else 0,
        }
        try:
            conn.execute('''
                UPDATE daily_entries SET
                    title=?, content=?, work_hours=?, tasks_completed=?, tasks_planned=?,
                    challenges=?, learnings=?, tags=?, mood=?, is_workday=?,
                    updated_at=datetime('now','localtime')
                WHERE entry_date=?
            ''', (data['title'], data['content'], data['work_hours'], data['tasks_completed'],
                  data['tasks_planned'], data['challenges'], data['learnings'], data['tags'],
                  data['mood'], data['is_workday'], date_str))
            conn.commit()
            flash(f'{date_str} 日报已更新', 'success')
        except Exception as e:
            conn.rollback()
            conn.close()
            flash(f'保存失败：{e}', 'error')
            return render_template('daily_create.html', entry=data, prefilled_date=date_str)
        conn.close()
        return redirect(url_for('daily_list'))

    conn.close()
    return render_template('daily_create.html', entry=entry, prefilled_date=date_str)


@app.route('/daily/<date_str>/delete', methods=['POST'])
def daily_delete(date_str):
    conn = get_db()
    conn.execute('DELETE FROM daily_entries WHERE entry_date = ?', (date_str,))
    conn.commit()
    conn.close()
    flash(f'{date_str} 日报已删除', 'success')
    return redirect(url_for('daily_list'))


@app.route('/daily/list')
def daily_list():
    page, per_page = _get_page_args()

    # 筛选参数
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    search = request.args.get('search', '').strip()
    tag_filter = request.args.get('tag', '').strip()

    # 构建查询
    where_clauses = []
    params = []

    if date_from:
        where_clauses.append('entry_date >= ?')
        params.append(date_from)
    if date_to:
        where_clauses.append('entry_date <= ?')
        params.append(date_to)
    if search:
        where_clauses.append('(title LIKE ? OR content LIKE ? OR tasks_completed LIKE ?)')
        params.extend([f'%{search}%', f'%{search}%', f'%{search}%'])
    if tag_filter:
        where_clauses.append('tags LIKE ?')
        params.append(f'%{tag_filter}%')

    where_sql = ' AND '.join(where_clauses) if where_clauses else '1=1'

    conn = get_db()
    total = conn.execute(
        f'SELECT COUNT(*) FROM daily_entries WHERE {where_sql}', params
    ).fetchone()[0]

    offset = (page - 1) * per_page
    rows = conn.execute(
        f'SELECT * FROM daily_entries WHERE {where_sql} ORDER BY entry_date DESC LIMIT ? OFFSET ?',
        params + [per_page, offset]
    ).fetchall()
    entries = [dict(r) for r in rows]

    # 所有标签
    all_tags_rows = conn.execute('SELECT DISTINCT tags FROM daily_entries WHERE tags != ""').fetchall()
    all_tags = set()
    for r in all_tags_rows:
        for t in r['tags'].split(','):
            t = t.strip()
            if t:
                all_tags.add(t)
    all_tags = sorted(all_tags)
    conn.close()

    total_pages = max(1, (total + per_page - 1) // per_page)
    start_p = max(1, page - 2)
    end_p = min(total_pages, page + 2)
    page_range = list(range(start_p, end_p + 1))

    return render_template('daily_list.html',
                           entries=entries, page=page, per_page=per_page,
                           total=total, total_pages=total_pages,
                           all_tags=all_tags,
                           date_from=date_from, date_to=date_to,
                           search=search, tag_filter=tag_filter,
                           page_range=page_range)


# ============================================================
# 日历视图
# ============================================================
@app.route('/daily/calendar')
def daily_calendar():
    today = date.today()
    year = request.args.get('year', today.year, type=int)
    month = request.args.get('month', today.month, type=int)
    settings = get_settings()
    week_start_day = int(settings.get('weekly_start_day', 0))

    grid = get_calendar_grid(year, month, week_start_day)

    # 本月统计
    conn = get_db()
    month_count = conn.execute(
        'SELECT COUNT(*) FROM daily_entries WHERE entry_date LIKE ?',
        (f'{year}-{month:02d}%',)
    ).fetchone()[0]
    month_workdays = conn.execute(
        'SELECT COUNT(*) FROM daily_entries WHERE entry_date LIKE ? AND is_workday=1',
        (f'{year}-{month:02d}%',)
    ).fetchone()[0]
    conn.close()

    return render_template('daily_calendar.html',
                           year=year, month=month,
                           grid=grid, today=today,
                           week_start_day=week_start_day,
                           month_count=month_count,
                           month_workdays=month_workdays)


@app.route('/api/daily/month/<int:year>/<int:month>')
def api_daily_month(year, month):
    """JSON API：返回某月所有日报摘要"""
    conn = get_db()
    rows = conn.execute(
        'SELECT entry_date, title, mood, is_workday, work_hours, content FROM daily_entries WHERE entry_date LIKE ? ORDER BY entry_date',
        (f'{year}-{month:02d}%',)
    ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


# ============================================================
# 周报
# ============================================================
@app.route('/report/weekly', methods=['GET', 'POST'])
def report_weekly():
    settings = get_settings()
    if not settings.get('start_date'):
        flash('请先设置实习信息', 'error')
        return redirect(url_for('settings_page'))

    start_date = parse_date(settings['start_date'])
    end_date = parse_date(settings['end_date'])
    week_start_day = int(settings.get('weekly_start_day', 0))
    all_weeks = get_all_week_starts(start_date, end_date, week_start_day)

    conn = get_db()
    existing = conn.execute(
        'SELECT id, week_start, is_finalized FROM weekly_reports ORDER BY week_start'
    ).fetchall()
    existing_map = {r['week_start']: r for r in existing}
    conn.close()

    weeks = []
    for ws in all_weeks:
        we = ws + timedelta(days=6)
        ws_str = format_date(ws)
        label = get_week_label(ws)
        week_num = get_internship_week_number(ws, start_date)
        er = existing_map.get(ws_str)
        weeks.append({
            'week_start': ws_str,
            'week_end': format_date(we),
            'label': label,
            'week_number': week_num,
            'has_report': er is not None,
            'report_id': er['id'] if er else None,
            'is_finalized': er['is_finalized'] if er else False,
        })

    today = date.today()
    current_week_start, _ = get_week_boundaries(today, week_start_day)
    current_ws = format_date(current_week_start)

    return render_template('report_weekly.html', weeks=weeks, current_week_start=current_ws)


@app.route('/report/weekly/<int:report_id>', methods=['GET', 'POST'])
def report_weekly_detail(report_id):
    conn = get_db()
    row = conn.execute('SELECT * FROM weekly_reports WHERE id = ?', (report_id,)).fetchone()
    if not row:
        conn.close()
        flash('周报不存在', 'error')
        return redirect(url_for('report_weekly'))
    report = dict(row)

    if request.method == 'POST':
        summary = request.form.get('summary', '')
        highlights = request.form.get('work_highlights', '')
        plan = request.form.get('next_week_plan', '')
        is_finalized = 1 if request.form.get('is_finalized') else 0
        conn.execute('''
            UPDATE weekly_reports SET summary=?, work_highlights=?, next_week_plan=?,
            is_finalized=?, updated_at=datetime('now','localtime')
            WHERE id=?
        ''', (summary, highlights, plan, is_finalized, report_id))
        conn.commit()
        msg = '周报已定稿' if is_finalized else '周报已保存'
        flash(msg, 'success')
        conn.close()
        return redirect(url_for('report_weekly_detail', report_id=report_id))

    dailies = conn.execute(
        'SELECT * FROM daily_entries WHERE entry_date BETWEEN ? AND ? ORDER BY entry_date',
        (report['week_start'], report['week_end'])
    ).fetchall()
    dailies = [dict(d) for d in dailies]
    conn.close()

    return render_template('report_weekly.html', report=report, dailies=dailies, view_detail=True)


@app.route('/report/weekly/generate', methods=['POST'])
def report_weekly_generate():
    from reports import generate_weekly_report
    week_start = request.form.get('week_start', '')
    if not week_start:
        flash('缺少周起始日期', 'error')
        return redirect(url_for('report_weekly'))

    report_id = generate_weekly_report(week_start)
    flash('周报已自动生成，你可以修改后定稿', 'success')
    return redirect(url_for('report_weekly_detail', report_id=report_id))


# ============================================================
# 月报
# ============================================================
@app.route('/report/monthly', methods=['GET', 'POST'])
def report_monthly():
    settings = get_settings()
    if not settings.get('start_date'):
        flash('请先设置实习信息', 'error')
        return redirect(url_for('settings_page'))

    start_date = parse_date(settings['start_date'])
    end_date = parse_date(settings['end_date'])
    today = date.today()

    months = []
    current = date(start_date.year, start_date.month, 1)
    final = date(end_date.year, end_date.month, 1)
    while current <= final:
        months.append({'year': current.year, 'month': current.month,
                      'label': month_label(current.year, current.month),
                      'name': f'{current.year}年{current.month}月'})
        if current.month == 12:
            current = date(current.year + 1, 1, 1)
        else:
            current = date(current.year, current.month + 1, 1)

    conn = get_db()
    existing = conn.execute('SELECT id, report_year, report_month, is_finalized FROM monthly_reports').fetchall()
    existing_map = {(r['report_year'], r['report_month']): r for r in existing}
    conn.close()

    for m in months:
        key = (m['year'], m['month'])
        er = existing_map.get(key)
        m['has_report'] = er is not None
        m['report_id'] = er['id'] if er else None
        m['is_finalized'] = er['is_finalized'] if er else False

    return render_template('report_monthly.html', months=months,
                           current_year=today.year, current_month=today.month)


@app.route('/report/monthly/<int:report_id>', methods=['GET', 'POST'])
def report_monthly_detail(report_id):
    conn = get_db()
    row = conn.execute('SELECT * FROM monthly_reports WHERE id = ?', (report_id,)).fetchone()
    if not row:
        conn.close()
        flash('月报不存在', 'error')
        return redirect(url_for('report_monthly'))
    report = dict(row)

    if request.method == 'POST':
        is_finalized = 1 if request.form.get('is_finalized') else 0
        conn.execute('''
            UPDATE monthly_reports SET summary=?, achievements=?, skills_gained=?,
            reflection=?, is_finalized=?, updated_at=datetime('now','localtime')
            WHERE id=?
        ''', (
            request.form.get('summary', ''),
            request.form.get('achievements', ''),
            request.form.get('skills_gained', ''),
            request.form.get('reflection', ''),
            is_finalized, report_id
        ))
        conn.commit()
        msg = '月报已定稿' if is_finalized else '月报已保存'
        flash(msg, 'success')
    conn.close()
    return render_template('report_monthly.html', report=report, view_detail=True)


@app.route('/report/monthly/generate', methods=['POST'])
def report_monthly_generate():
    from reports import generate_monthly_report
    year = int(request.form.get('year', date.today().year))
    month = int(request.form.get('month', date.today().month))
    report_id = generate_monthly_report(year, month)
    flash('月报已自动生成，你可以修改后定稿', 'success')
    return redirect(url_for('report_monthly_detail', report_id=report_id))


# ============================================================
# 年报
# ============================================================
@app.route('/report/annual', methods=['GET', 'POST'])
def report_annual():
    settings = get_settings()
    if not settings.get('start_date'):
        flash('请先设置实习信息', 'error')
        return redirect(url_for('settings_page'))

    start_date = parse_date(settings['start_date'])
    end_date = parse_date(settings['end_date'])
    years = list(range(start_date.year, end_date.year + 1))

    conn = get_db()
    existing = conn.execute('SELECT id, report_year, is_finalized FROM annual_reports').fetchall()
    existing_map = {r['report_year']: r for r in existing}
    conn.close()

    year_list = [{'year': y,
                  'has_report': y in existing_map,
                  'report_id': existing_map.get(y, {}).get('id') if y in existing_map else None,
                  'is_finalized': existing_map[y]['is_finalized'] if y in existing_map else False}
                 for y in years]

    return render_template('report_annual.html', years=year_list, current_year=date.today().year)


@app.route('/report/annual/<int:report_id>', methods=['GET', 'POST'])
def report_annual_detail(report_id):
    conn = get_db()
    row = conn.execute('SELECT * FROM annual_reports WHERE id = ?', (report_id,)).fetchone()
    if not row:
        conn.close()
        flash('年报不存在', 'error')
        return redirect(url_for('report_annual'))
    report = dict(row)

    if request.method == 'POST':
        is_finalized = 1 if request.form.get('is_finalized') else 0
        conn.execute('''
            UPDATE annual_reports SET summary=?, overall_review=?, key_projects=?,
            growth_summary=?, future_outlook=?, is_finalized=?,
            updated_at=datetime('now','localtime')
            WHERE id=?
        ''', (
            request.form.get('summary', ''),
            request.form.get('overall_review', ''),
            request.form.get('key_projects', ''),
            request.form.get('growth_summary', ''),
            request.form.get('future_outlook', ''),
            is_finalized, report_id
        ))
        conn.commit()
        msg = '年报已定稿' if is_finalized else '年报已保存'
        flash(msg, 'success')
    conn.close()
    return render_template('report_annual.html', report=report, view_detail=True)


@app.route('/report/annual/generate', methods=['POST'])
def report_annual_generate():
    from reports import generate_annual_report
    year = int(request.form.get('year', date.today().year))
    report_id = generate_annual_report(year)
    flash('年报已自动生成，你可以修改后定稿', 'success')
    return redirect(url_for('report_annual_detail', report_id=report_id))


# ============================================================
# 导出
# ============================================================
@app.route('/export/word/<report_type>/<int:report_id>')
def export_word(report_type, report_id):
    from export import export_to_docx
    buffer = export_to_docx(report_type, report_id)
    filename = _export_filename(report_type, report_id)
    return Response(
        buffer.getvalue(),
        mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        headers={'Content-Disposition': f'attachment; filename="{filename}.docx"'}
    )


@app.route('/export/pdf/<report_type>/<int:report_id>')
def export_pdf(report_type, report_id):
    from export import export_to_pdf
    try:
        pdf_bytes = export_to_pdf(report_type, report_id)
        filename = _export_filename(report_type, report_id)
        return Response(
            pdf_bytes,
            mimetype='application/pdf',
            headers={'Content-Disposition': f'attachment; filename="{filename}.pdf"'}
        )
    except Exception:
        return _export_html_fallback(report_type, report_id)


# ============================================================
# 数据备份与恢复
# ============================================================
@app.route('/api/backup', methods=['GET'])
def api_backup():
    """导出整个数据库为 JSON"""
    conn = get_db()
    data = {
        'version': '1.0',
        'exported_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'settings': dict(conn.execute('SELECT * FROM settings WHERE id=1').fetchone() or {}),
        'daily_entries': [dict(r) for r in conn.execute('SELECT * FROM daily_entries ORDER BY entry_date').fetchall()],
        'weekly_reports': [dict(r) for r in conn.execute('SELECT * FROM weekly_reports ORDER BY week_start').fetchall()],
        'monthly_reports': [dict(r) for r in conn.execute('SELECT * FROM monthly_reports ORDER BY report_year, report_month').fetchall()],
        'annual_reports': [dict(r) for r in conn.execute('SELECT * FROM annual_reports ORDER BY report_year').fetchall()],
    }
    conn.close()

    json_str = json.dumps(data, ensure_ascii=False, indent=2)
    filename = f'backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
    return Response(
        json_str,
        mimetype='application/json; charset=utf-8',
        headers={'Content-Disposition': f'attachment; filename="{filename}"'}
    )


@app.route('/api/restore', methods=['POST'])
def api_restore():
    """从 JSON 恢复数据库"""
    file = request.files.get('backup_file')
    if not file:
        flash('请选择备份文件', 'error')
        return redirect(url_for('settings_page'))

    try:
        data = json.loads(file.read().decode('utf-8'))
    except Exception:
        flash('无效的备份文件', 'error')
        return redirect(url_for('settings_page'))

    conn = get_db()
    # 恢复设置
    if data.get('settings'):
        s = data['settings']
        conn.execute('''
            INSERT OR REPLACE INTO settings (id, student_name, student_id, school, major,
                company_name, position, department, mentor_name, start_date, end_date,
                weekly_start_day, updated_at)
            VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now','localtime'))
        ''', (s.get('student_name',''), s.get('student_id',''), s.get('school',''),
              s.get('major',''), s.get('company_name',''), s.get('position',''),
              s.get('department',''), s.get('mentor_name',''),
              s.get('start_date',''), s.get('end_date',''),
              s.get('weekly_start_day', 0)))

    # 恢复日报
    for e in data.get('daily_entries', []):
        conn.execute('''
            INSERT OR REPLACE INTO daily_entries
            (entry_date, title, content, work_hours, tasks_completed, tasks_planned,
             challenges, learnings, tags, mood, is_workday, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now','localtime'))
        ''', (e['entry_date'], e.get('title',''), e.get('content',''),
              e.get('work_hours',8), e.get('tasks_completed',''), e.get('tasks_planned',''),
              e.get('challenges',''), e.get('learnings',''), e.get('tags',''),
              e.get('mood',3), e.get('is_workday',1)))

    # 恢复报告
    for r in data.get('weekly_reports', []):
        conn.execute('''
            INSERT OR REPLACE INTO weekly_reports
            (id, week_start, week_end, week_number, summary, work_highlights,
             next_week_plan, is_finalized, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now','localtime'))
        ''', (r['id'], r['week_start'], r['week_end'], r['week_number'],
              r.get('summary',''), r.get('work_highlights',''),
              r.get('next_week_plan',''), r.get('is_finalized',0)))

    for r in data.get('monthly_reports', []):
        conn.execute('''
            INSERT OR REPLACE INTO monthly_reports
            (id, report_month, report_year, month_label, summary, achievements,
             skills_gained, reflection, is_finalized, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now','localtime'))
        ''', (r['id'], r['report_month'], r['report_year'], r['month_label'],
              r.get('summary',''), r.get('achievements',''),
              r.get('skills_gained',''), r.get('reflection',''), r.get('is_finalized',0)))

    for r in data.get('annual_reports', []):
        conn.execute('''
            INSERT OR REPLACE INTO annual_reports
            (id, report_year, summary, overall_review, key_projects,
             growth_summary, future_outlook, is_finalized, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now','localtime'))
        ''', (r['id'], r['report_year'], r.get('summary',''),
              r.get('overall_review',''), r.get('key_projects',''),
              r.get('growth_summary',''), r.get('future_outlook',''),
              r.get('is_finalized',0)))

    conn.commit()
    conn.close()
    flash('数据已成功恢复', 'success')
    return redirect(url_for('settings_page'))


def _export_filename(report_type, report_id):
    settings = get_settings()
    name = settings.get('student_name', '学生')
    type_labels = {'weekly': '周报', 'monthly': '月报', 'annual': '年报'}
    label = type_labels.get(report_type, '报告')

    conn = get_db()
    if report_type == 'weekly':
        row = conn.execute('SELECT * FROM weekly_reports WHERE id = ?', (report_id,)).fetchone()
        if row:
            return f'实习{label}_{row["week_start"]}_{name}'
    elif report_type == 'monthly':
        row = conn.execute('SELECT * FROM monthly_reports WHERE id = ?', (report_id,)).fetchone()
        if row:
            return f'实习{label}_{row["month_label"]}_{name}'
    elif report_type == 'annual':
        row = conn.execute('SELECT * FROM annual_reports WHERE id = ?', (report_id,)).fetchone()
        if row:
            return f'实习{label}_{row["report_year"]}_{name}'
    conn.close()
    return f'实习{label}_{name}'


def _export_html_fallback(report_type, report_id):
    from export import render_report_html
    html = render_report_html(report_type, report_id)
    return Response(html, mimetype='text/html')


# ============================================================
# 启动
# ============================================================
if __name__ == '__main__':
    print('实习工作记录器 启动中...')
    print('访问 http://127.0.0.1:5000')
    app.run(host='127.0.0.1', port=5000, debug=True)
