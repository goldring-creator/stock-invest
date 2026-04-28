"""
SQLite 데이터베이스 스키마 초기화 및 공통 연결 관리
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "08_데이터" / "stock.db"


def get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    with get_conn() as conn:
        conn.executescript("""
        -- 일별 OHLCV + 밸류에이션
        CREATE TABLE IF NOT EXISTS daily_price (
            ticker      TEXT NOT NULL,
            date        TEXT NOT NULL,
            open        INTEGER,
            high        INTEGER,
            low         INTEGER,
            close       INTEGER,
            volume      INTEGER,
            per         REAL,
            pbr         REAL,
            div_yield   REAL,
            created_at  TEXT DEFAULT (datetime('now', 'localtime')),
            PRIMARY KEY (ticker, date)
        );

        -- DART 재무제표 (분기별)
        CREATE TABLE IF NOT EXISTS financial_statement (
            ticker      TEXT NOT NULL,
            period      TEXT NOT NULL,   -- 예: 2024Q4
            account     TEXT NOT NULL,   -- 예: 매출액, 영업이익
            value       REAL,
            unit        TEXT DEFAULT '원',
            created_at  TEXT DEFAULT (datetime('now', 'localtime')),
            PRIMARY KEY (ticker, period, account)
        );

        -- 뉴스 감성 점수
        CREATE TABLE IF NOT EXISTS news_sentiment (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker      TEXT NOT NULL,
            date        TEXT NOT NULL,
            title       TEXT,
            url         TEXT,
            score       REAL,           -- -1.0(부정) ~ +1.0(긍정)
            summary     TEXT,
            created_at  TEXT DEFAULT (datetime('now', 'localtime'))
        );
        CREATE INDEX IF NOT EXISTS idx_news_ticker_date ON news_sentiment(ticker, date);

        -- 버핏 가디언 판단 로그
        CREATE TABLE IF NOT EXISTS buffett_decisions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker      TEXT NOT NULL,
            date        TEXT NOT NULL,
            decision    TEXT NOT NULL,  -- APPROVE / REJECT / FLAG
            score       INTEGER,        -- 0~100
            reason      TEXT,
            citations   TEXT,           -- 버핏 서한 인용 (JSON 배열)
            created_at  TEXT DEFAULT (datetime('now', 'localtime'))
        );

        -- 매매 주문 로그
        CREATE TABLE IF NOT EXISTS trade_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker      TEXT NOT NULL,
            date        TEXT NOT NULL,
            order_type  TEXT NOT NULL,  -- BUY / SELL
            quantity    INTEGER,
            price       INTEGER,
            amount      INTEGER,
            order_id    TEXT,           -- KIS 주문번호
            status      TEXT DEFAULT 'PENDING',  -- PENDING / FILLED / CANCELLED
            created_at  TEXT DEFAULT (datetime('now', 'localtime'))
        );
        """)
    print(f"[database] DB 초기화 완료: {DB_PATH}")


if __name__ == "__main__":
    init_db()
