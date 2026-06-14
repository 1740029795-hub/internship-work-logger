"""
报告自动生成逻辑 v2
周报 → 月报 → 年报 级联聚合，结构化模板
"""
import re
from datetime import date, timedelta
from database import get_db, get_settings
from calendar_utils import parse_date, format_date, get_week_boundaries, get_month_boundaries

# 中文停用词表
_STOP_WORDS = {
    '的','了','在','是','我','有','和','就','不','人','都','一','一个','上','也','很','到',
    '说','要','去','你','会','着','没有','看','好','自己','这','他','她','它','们','那','些',
    '所','被','把','让','从','对','等','等等','以及','或','与','但','而','且','虽然','因为',
    '所以','如果','可以','进行','使用','通过','需要','已经','目前','今天','昨天','明天',
    '这周','本周','下周','主要','完成','工作','任务','学习','了解','掌握','熟悉','参与',
    '负责','处理','解决','问题','公司','项目','相关','业务','技术','开发','测试','我们',
    '他们','大家','这个','那个','比较','非常','不是','还是','如何','怎么','什么','哪些',
    '其中','之后','之前','继续','开始','结束','能够','不同','一样','来说','对于','作为',
    '利用','帮助','实现','包括','提供','提高','增加','减少','改进','优化','完善','调整',
    '修改','更新','重构','部署','上线','发布','测试','调试','修复','排查'
}

_WORD_SPLITTER = re.compile(r'[，。！？、\s\n\r,.!?;:；：（）()\[\]【】"\'""''/|#@&*+=<>～~]+')


def _extract_keywords(texts, top_n=8):
    """简单关键词提取：TF 计数 + 停用词过滤 + 长度偏好"""
    word_freq = {}
    for text in texts:
        if not text:
            continue
        words = _WORD_SPLITTER.split(text)
        for w in words:
            w = w.strip()
            if len(w) < 2 or w in _STOP_WORDS or w.isdigit():
                continue
            word_freq[w] = word_freq.get(w, 0) + 1

    sorted_words = sorted(word_freq.items(), key=lambda x: (-x[1], -len(x[0])))
    return [w for w, _ in sorted_words[:top_n]]


def _daily_list_summary(dailies):
    """从日报列表提取结构化摘要"""
    if not dailies:
        return None

    work_days = len(dailies)
    total_hours = sum(d.get('work_hours', 0) for d in dailies)
    moods = [d.get('mood', 3) for d in dailies if d.get('mood')]
    avg_mood = round(sum(moods) / len(moods), 1) if moods else 3

    all_contents = [d.get('content', '') for d in dailies]
    all_titles = [d.get('title', '') for d in dailies]
    all_tags = []
    for d in dailies:
        if d.get('tags'):
            all_tags.extend([t.strip() for t in d['tags'].split(',') if t.strip()])

    keywords = _extract_keywords(all_contents + all_titles + all_tags, top_n=6)

    return {
        'work_days': work_days,
        'total_hours': round(total_hours, 1),
        'avg_mood': avg_mood,
        'keywords': keywords,
        'all_tasks': _extract_tasks_list(dailies),
        'all_learnings': _extract_learnings_list(dailies),
        'all_challenges': _extract_challenges_list(dailies),
    }


def _extract_tasks_list(dailies):
    """提取所有完成任务"""
    tasks = []
    for d in dailies:
        if d.get('tasks_completed'):
            for t in d['tasks_completed'].split('\n'):
                t = t.strip()
                if t and len(t) > 2:
                    tasks.append(t)
    return tasks


def _extract_learnings_list(dailies):
    """提取所有学习收获"""
    items = []
    for d in dailies:
        if d.get('learnings'):
            items.append({'date': d['entry_date'], 'text': d['learnings'].strip()})
    return items


def _extract_challenges_list(dailies):
    """提取所有困难"""
    items = []
    for d in dailies:
        if d.get('challenges'):
            items.append({'date': d['entry_date'], 'text': d['challenges'].strip()})
    return items


def generate_weekly_report(week_start_str):
    """根据日报自动生成周报"""
    settings = get_settings()
    week_start_day = int(settings.get('weekly_start_day', 0))
    ws = parse_date(week_start_str)
    we = ws + timedelta(days=6)
    we_str = format_date(we)

    conn = get_db()
    rows = conn.execute(
        'SELECT * FROM daily_entries WHERE entry_date BETWEEN ? AND ? AND is_workday=1 ORDER BY entry_date',
        (week_start_str, we_str)
    ).fetchall()
    dailies = [dict(r) for r in rows]
    conn.close()

    week_num = 1
    if settings.get('start_date'):
        intern_start = parse_date(settings['start_date'])
        week_num = max(1, (ws - intern_start).days // 7 + 1)

    if not dailies:
        summary = f'本周（{week_start_str} 至 {we_str}）暂无实习记录。'
        highlights = '（无）'
        plan = '（待填写）'
    else:
        info = _daily_list_summary(dailies)
        keyword_str = '、'.join(info['keywords'][:5]) if info['keywords'] else '多项工作'
        mood_labels = {1: '较低', 2: '一般', 3: '正常', 4: '较高', 5: '很高'}

        # 构建结构化周报摘要
        summary = (
            f'一、工作概况\n'
            f'本周（{week_start_str} 至 {we_str}）共完成 {info["work_days"]} 天实习，'
            f'累计工时 {info["total_hours"]} 小时。'
            f'主要涉及 {keyword_str} 等工作内容。'
            f'本周工作状态{mood_labels.get(round(info["avg_mood"]), "正常")}。\n\n'
        )

        # 添加每日简述
        summary += '二、每日概要\n'
        for d in dailies:
            title = d.get('title', '无标题')
            content = d.get('content', '')
            brief = content[:60] + ('...' if len(content) > 60 else '')
            summary += f'{d["entry_date"]}：{title}'
            if brief:
                summary += f' — {brief}'
            summary += f'（{d["work_hours"]}h）\n'

        # 工作亮点
        if info['all_tasks']:
            highlights = '本周完成的主要任务：\n'
            seen = set()
            for t in info['all_tasks'][:12]:
                if t not in seen:
                    highlights += f'- {t}\n'
                    seen.add(t)
        else:
            highlights = '本周无详细的完成任务记录，建议在日报中补充。'

        # 下周计划
        latest = dailies[-1]
        if latest.get('tasks_planned') and latest['tasks_planned'].strip():
            plan = latest['tasks_planned'].strip()
        else:
            plan = '（待制定）根据本周工作进展，请规划下周工作重点。'

    conn = get_db()
    conn.execute('''
        INSERT OR REPLACE INTO weekly_reports
        (week_start, week_end, week_number, summary, work_highlights, next_week_plan,
         generated_from_dailies, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, 1, datetime('now','localtime'))
    ''', (week_start_str, we_str, week_num, summary, highlights, plan))
    conn.commit()
    report_id = conn.execute(
        'SELECT id FROM weekly_reports WHERE week_start = ?', (week_start_str,)
    ).fetchone()['id']
    conn.close()
    return report_id


def generate_monthly_report(year, month):
    """根据周报（优先）或日报自动生成月报"""
    month_start, month_end = get_month_boundaries(year, month)
    ms_str = format_date(month_start)
    me_str = format_date(month_end)
    month_name = f'{year}年{month}月'

    conn = get_db()

    # 尝试从周报聚合
    weekly_rows = conn.execute(
        'SELECT * FROM weekly_reports WHERE week_start BETWEEN ? AND ? OR week_end BETWEEN ? AND ? ORDER BY week_start',
        (ms_str, me_str, ms_str, me_str)
    ).fetchall()
    weeklies = [dict(r) for r in weekly_rows]

    # 获取日报
    daily_rows = conn.execute(
        'SELECT * FROM daily_entries WHERE entry_date BETWEEN ? AND ? AND is_workday=1 ORDER BY entry_date',
        (ms_str, me_str)
    ).fetchall()
    dailies = [dict(r) for r in daily_rows]
    conn.close()

    if not dailies and not weeklies:
        summary = f'{month_name}暂无实习记录。'
        achievements = '（无）'
        skills_gained = '（无）'
        reflection = '（待填写）'
    else:
        info = _daily_list_summary(dailies) if dailies else None

        # 月度总结
        summary = f'{month_name}实习总结：\n\n'
        if info:
            keyword_str = '、'.join(info['keywords'][:5]) if info['keywords'] else '多项工作'
            summary += f'本月共完成 {info["work_days"]} 天实习，累计 {info["total_hours"]} 小时。'
            summary += f'工作重点集中在 {keyword_str} 等方面。\n'

        # 如果有周报，追加各周摘要
        if weeklies:
            summary += '\n各周回顾：\n'
            for w in weeklies:
                first_line = w['summary'].split('\n')[0] if w['summary'] else '（无内容）'
                summary += f'- 第{w["week_number"]}周：{first_line}\n'

        # 主要成果
        if weeklies:
            achievements = ''
            for w in weeklies:
                if w.get('work_highlights') and w['work_highlights'] not in ('（无）', '（无具体任务记录）', ''):
                    achievements += f'第{w["week_number"]}周：\n{w["work_highlights"]}\n\n'
            if not achievements.strip():
                achievements = _format_achievements_from_dailies(dailies)
        else:
            achievements = _format_achievements_from_dailies(dailies)

        # 技能收获
        if info and info['all_learnings']:
            skills_gained = '本月学习与收获：\n'
            for item in info['all_learnings'][:8]:
                skills_gained += f'- [{item["date"]}] {item["text"]}\n'
        else:
            skills_gained = '（请根据本月学习情况补充技能收获）'

        # 反思
        if info and info['all_challenges']:
            reflection = '遇到的问题与思考：\n'
            for item in info['all_challenges'][:6]:
                reflection += f'- [{item["date"]}] {item["text"]}\n'
            reflection += '\n建议：针对以上问题，在下月工作中重点关注和改进。'
        else:
            reflection = '（请补充本月遇到的困难和反思）'

    conn = get_db()
    conn.execute('''
        INSERT OR REPLACE INTO monthly_reports
        (report_month, report_year, month_label, summary, achievements, skills_gained, reflection, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now','localtime'))
    ''', (month, year, f'{year}-{month:02d}', summary, achievements, skills_gained, reflection))
    conn.commit()
    report_id = conn.execute(
        'SELECT id FROM monthly_reports WHERE report_year = ? AND report_month = ?', (year, month)
    ).fetchone()['id']
    conn.close()
    return report_id


def _format_achievements_from_dailies(dailies):
    """从日报格式化成果"""
    tasks = _extract_tasks_list(dailies)
    if not tasks:
        return '（无具体任务记录）'
    seen = set()
    result = '本月完成的主要任务：\n'
    for t in tasks[:15]:
        if t not in seen:
            result += f'- {t}\n'
            seen.add(t)
    return result


def generate_annual_report(year):
    """根据月报自动生成年报"""
    conn = get_db()

    monthly_rows = conn.execute(
        'SELECT * FROM monthly_reports WHERE report_year = ? ORDER BY report_month', (year,)
    ).fetchall()
    monthlies = [dict(r) for r in monthly_rows]

    # 自动补全缺失的月报
    existing_months = {r['report_month'] for r in monthlies}
    for m in range(1, 13):
        if m not in existing_months:
            has_dailies = conn.execute(
                'SELECT COUNT(*) FROM daily_entries WHERE entry_date LIKE ?',
                (f'{year}-{m:02d}%',)
            ).fetchone()[0]
            if has_dailies > 0:
                conn.close()
                mid = generate_monthly_report(year, m)
                conn = get_db()

    # 重新获取
    monthly_rows = conn.execute(
        'SELECT * FROM monthly_reports WHERE report_year = ? ORDER BY report_month', (year,)
    ).fetchall()
    monthlies = [dict(r) for r in monthly_rows]

    if not monthlies:
        summary = f'{year}年暂无实习记录。'
        overall_review = '（待填写）'
        key_projects = '（待填写）'
        growth_summary = '（待填写）'
        future_outlook = '（待填写）'
    else:
        # 提取所有工作天数
        total_days = 0
        for m in monthlies:
            match = re.search(r'共完成 (\d+) 天', m.get('summary', ''))
            if match:
                total_days += int(match.group(1))

        summary = f'{year}年全年实习总结：共约 {total_days} 个工作日，覆盖 {len(monthlies)} 个月度。'

        # 总体回顾：按时间线
        overall_review = f'{year}年实习总体回顾：\n\n'
        for m in monthlies:
            first_line = m['summary'].split('\n')[0] if m['summary'] else ''
            overall_review += f'{m["report_month"]}月：{first_line}\n'

        # 重点项目：从所有月报聚合成果
        all_achievements = []
        for m in monthlies:
            ach = m.get('achievements', '')
            if ach and '（无' not in ach and '（请' not in ach:
                all_achievements.append(f'{m["report_month"]}月成果：\n{ach}')
        key_projects = '\n\n'.join(all_achievements[:6]) if all_achievements else '（请补充本年度参与的重点项目）'

        # 成长总结
        all_skills = []
        for m in monthlies:
            sk = m.get('skills_gained', '')
            if sk and '（请' not in sk and '（无' not in sk:
                all_skills.append(sk)
        if all_skills:
            growth_summary = '年度技能成长轨迹：\n\n'
            for i, sk in enumerate(all_skills[:6]):
                growth_summary += f'{sk}\n'
        else:
            growth_summary = '（请总结本年度的成长和收获）'

        # 未来展望
        future_outlook = (
            f'经过{year}年的实习，在专业技能和职场素养方面都取得了显著进步。'
            f'未来将在以下方面继续努力：\n'
            f'1. 深化专业领域的技术积累\n'
            f'2. 提升项目管理和团队协作能力\n'
            f'3. 增强解决复杂问题的系统性思维\n'
            f'4. 拓展行业视野和人脉网络\n\n'
            f'（请根据实际情况补充具体展望）'
        )

    conn.execute('''
        INSERT OR REPLACE INTO annual_reports
        (report_year, summary, overall_review, key_projects, growth_summary, future_outlook, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, datetime('now','localtime'))
    ''', (year, summary, overall_review, key_projects, growth_summary, future_outlook))
    conn.commit()
    report_id = conn.execute(
        'SELECT id FROM annual_reports WHERE report_year = ?', (year,)
    ).fetchone()['id']
    conn.close()
    return report_id
