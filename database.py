"""
数据库初始化与工具函数
SQLite 数据库，WAL 模式，5 张表：settings / daily_entries / weekly_reports / monthly_reports / annual_reports
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'internship.db')


def get_db():
    """获取数据库连接，启用 WAL 模式和外键"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA cache_size=-8000")
    return conn


def init_db():
    """初始化数据库，创建所有表（如果不存在）"""
    conn = get_db()
    cursor = conn.cursor()

    # --- 设置表 (单行，id 恒为1) ---
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            id               INTEGER PRIMARY KEY CHECK (id = 1),
            student_name     TEXT NOT NULL DEFAULT '',
            student_id       TEXT NOT NULL DEFAULT '',
            school           TEXT NOT NULL DEFAULT '',
            major            TEXT NOT NULL DEFAULT '',
            company_name     TEXT NOT NULL DEFAULT '',
            position         TEXT NOT NULL DEFAULT '',
            department       TEXT NOT NULL DEFAULT '',
            mentor_name      TEXT NOT NULL DEFAULT '',
            start_date       TEXT NOT NULL DEFAULT '',
            end_date         TEXT NOT NULL DEFAULT '',
            weekly_start_day INTEGER NOT NULL DEFAULT 0,
            created_at       TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            updated_at       TEXT NOT NULL DEFAULT (datetime('now','localtime'))
        )
    ''')

    # 插入默认设置行（如果不存在）
    cursor.execute('INSERT OR IGNORE INTO settings (id) VALUES (1)')

    # --- 日报表 ---
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS daily_entries (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            entry_date      TEXT NOT NULL UNIQUE,
            title           TEXT NOT NULL DEFAULT '',
            content         TEXT NOT NULL DEFAULT '',
            work_hours      REAL NOT NULL DEFAULT 8.0,
            tasks_completed TEXT NOT NULL DEFAULT '',
            tasks_planned   TEXT NOT NULL DEFAULT '',
            challenges      TEXT NOT NULL DEFAULT '',
            learnings       TEXT NOT NULL DEFAULT '',
            tags            TEXT NOT NULL DEFAULT '',
            mood            INTEGER NOT NULL DEFAULT 3,
            is_workday      INTEGER NOT NULL DEFAULT 1,
            created_at      TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            updated_at      TEXT NOT NULL DEFAULT (datetime('now','localtime'))
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_daily_date ON daily_entries(entry_date)')

    # --- 周报表 ---
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS weekly_reports (
            id                    INTEGER PRIMARY KEY AUTOINCREMENT,
            week_start            TEXT NOT NULL,
            week_end              TEXT NOT NULL,
            week_number           INTEGER NOT NULL,
            summary               TEXT NOT NULL DEFAULT '',
            work_highlights       TEXT NOT NULL DEFAULT '',
            next_week_plan        TEXT NOT NULL DEFAULT '',
            generated_from_dailies INTEGER NOT NULL DEFAULT 1,
            is_finalized          INTEGER NOT NULL DEFAULT 0,
            created_at            TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            updated_at            TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            UNIQUE(week_start)
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_weekly_range ON weekly_reports(week_start, week_end)')

    # --- 月报表 ---
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS monthly_reports (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            report_month    INTEGER NOT NULL,
            report_year     INTEGER NOT NULL,
            month_label     TEXT NOT NULL,
            summary         TEXT NOT NULL DEFAULT '',
            achievements    TEXT NOT NULL DEFAULT '',
            skills_gained   TEXT NOT NULL DEFAULT '',
            reflection      TEXT NOT NULL DEFAULT '',
            is_finalized    INTEGER NOT NULL DEFAULT 0,
            created_at      TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            updated_at      TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            UNIQUE(report_year, report_month)
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_monthly_ym ON monthly_reports(report_year, report_month)')

    # --- 年报表 ---
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS annual_reports (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            report_year     INTEGER NOT NULL UNIQUE,
            summary         TEXT NOT NULL DEFAULT '',
            overall_review  TEXT NOT NULL DEFAULT '',
            key_projects    TEXT NOT NULL DEFAULT '',
            growth_summary  TEXT NOT NULL DEFAULT '',
            future_outlook  TEXT NOT NULL DEFAULT '',
            is_finalized    INTEGER NOT NULL DEFAULT 0,
            created_at      TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            updated_at      TEXT NOT NULL DEFAULT (datetime('now','localtime'))
        )
    ''')

    conn.commit()
    conn.close()


def get_settings():
    """获取实习设置（单行）"""
    conn = get_db()
    row = conn.execute('SELECT * FROM settings WHERE id = 1').fetchone()
    conn.close()
    return dict(row) if row else {}


def save_settings(data):
    """保存实习设置"""
    conn = get_db()
    conn.execute('''
        UPDATE settings SET
            student_name=?, student_id=?, school=?, major=?,
            company_name=?, position=?, department=?, mentor_name=?,
            start_date=?, end_date=?, weekly_start_day=?,
            updated_at=datetime('now','localtime')
        WHERE id=1
    ''', (
        data.get('student_name', ''),
        data.get('student_id', ''),
        data.get('school', ''),
        data.get('major', ''),
        data.get('company_name', ''),
        data.get('position', ''),
        data.get('department', ''),
        data.get('mentor_name', ''),
        data.get('start_date', ''),
        data.get('end_date', ''),
        data.get('weekly_start_day', 0),
    ))
    conn.commit()
    conn.close()
