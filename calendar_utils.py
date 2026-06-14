"""
日历和日期计算工具函数
"""
from datetime import datetime, date, timedelta
import calendar


def parse_date(date_str):
    """解析 'YYYY-MM-DD' 字符串为 date 对象"""
    return datetime.strptime(date_str, '%Y-%m-%d').date()


def format_date(d):
    """将 date 对象格式化为 'YYYY-MM-DD'"""
    return d.strftime('%Y-%m-%d')


def get_week_boundaries(d, start_of_week=0):
    """
    获取 d 所在周的起止日期
    start_of_week: 0=周一, 6=周日
    """
    # Python 的 weekday(): 0=周一, 6=周日
    offset = d.weekday() - start_of_week
    if offset < 0:
        offset += 7
    week_start = d - timedelta(days=offset)
    week_end = week_start + timedelta(days=6)
    return week_start, week_end


def get_month_boundaries(year, month):
    """获取某月的起止日期"""
    first_day = date(year, month, 1)
    last_day = date(year, month, calendar.monthrange(year, month)[1])
    return first_day, last_day


def get_calendar_grid(year, month, start_of_week=0):
    """
    生成日历网格，返回 6 行 × 7 列的二维数组
    每个元素为 date 对象，包含上月/下月的填充日期
    """
    cal = calendar.Calendar(firstweekday=start_of_week)
    weeks = cal.monthdatescalendar(year, month)
    return weeks


def get_internship_week_number(d, start_date):
    """
    计算实习第几周 (1-based)
    如果 d < start_date，返回 1
    """
    if d < start_date:
        return 1
    days_diff = (d - start_date).days
    return days_diff // 7 + 1


def get_all_week_starts(start_date, end_date, start_of_week=0):
    """
    获取实习期间所有周的起始日期列表
    """
    start = parse_date(start_date) if isinstance(start_date, str) else start_date
    end = parse_date(end_date) if isinstance(end_date, str) else end_date

    # 找到第一个周起始日
    first_week_start, _ = get_week_boundaries(start, start_of_week)

    weeks = []
    current = first_week_start
    while current <= end:
        weeks.append(current)
        current += timedelta(days=7)
    return weeks


def get_week_label(week_start):
    """生成周标签，如 '2026W24'"""
    iso = week_start.isocalendar()
    return f'{iso[0]}W{iso[1]:02d}'


def month_label(year, month):
    """生成月标签，如 '2026-06'"""
    return f'{year}-{month:02d}'


def chinese_weekday(weekday):
    """返回中文星期名"""
    names = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
    return names[weekday] if 0 <= weekday <= 6 else ''
