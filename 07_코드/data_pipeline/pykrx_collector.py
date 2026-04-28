"""
pykrx 기반 일별 OHLCV + PER/PBR/배당수익률 수집기
실행: python pykrx_collector.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import date, timedelta
from typing import List
import time

from pykrx import stock as krx
from database import get_conn, init_db


# 코스피200 대표 종목 (초기 모니터링 대상 — 필요 시 확장)
DEFAULT_TICKERS = [
    "005930",  # 삼성전자
    "000660",  # SK하이닉스
    "005380",  # 현대차
    "035420",  # NAVER
    "051910",  # LG화학
    "006400",  # 삼성SDI
    "028260",  # 삼성물산
    "012330",  # 현대모비스
    "066570",  # LG전자
    "003550",  # LG
    "015760",  # 한국전력
    "096770",  # SK이노베이션
    "017670",  # SK텔레콤
    "032830",  # 삼성생명
    "086790",  # 하나금융지주
    "105560",  # KB금융
    "055550",  # 신한지주
    "316140",  # 우리금융지주
    "000270",  # 기아
    "003490",  # 대한항공
]


def collect_ohlcv(ticker: str, from_date: str, to_date: str) -> List[dict]:
    try:
        df = krx.get_market_ohlcv_by_date(from_date, to_date, ticker)
        if df.empty:
            return []
        rows = []
        for idx, row in df.iterrows():
            rows.append({
                "ticker": ticker,
                "date": idx.strftime("%Y-%m-%d"),
                "open": int(row.get("시가", 0) or 0),
                "high": int(row.get("고가", 0) or 0),
                "low": int(row.get("저가", 0) or 0),
                "close": int(row.get("종가", 0) or 0),
                "volume": int(row.get("거래량", 0) or 0),
            })
        return rows
    except Exception as e:
        print(f"  [pykrx] OHLCV 오류 {ticker}: {e}")
        return []


def collect_fundamental(ticker: str, from_date: str, to_date: str) -> dict:
    try:
        df = krx.get_market_fundamental_by_date(from_date, to_date, ticker)
        if df.empty:
            return {}
        result = {}
        for idx, row in df.iterrows():
            date_str = idx.strftime("%Y-%m-%d")
            result[date_str] = {
                "per": float(row.get("PER", 0) or 0),
                "pbr": float(row.get("PBR", 0) or 0),
                "div_yield": float(row.get("DIV", 0) or 0),
            }
        return result
    except Exception as e:
        print(f"  [pykrx] 펀더멘털 오류 {ticker}: {e}")
        return {}


def upsert_rows(rows: List[dict]):
    if not rows:
        return
    with get_conn() as conn:
        conn.executemany(
            """INSERT OR REPLACE INTO daily_price
               (ticker, date, open, high, low, close, volume, per, pbr, div_yield)
               VALUES (:ticker, :date, :open, :high, :low, :close, :volume,
                       :per, :pbr, :div_yield)""",
            rows
        )


def collect_all(tickers: List[str] = None, days_back: int = 30):
    if tickers is None:
        tickers = DEFAULT_TICKERS

    to_dt = date.today()
    from_dt = to_dt - timedelta(days=days_back)
    from_date = from_dt.strftime("%Y%m%d")
    to_date = to_dt.strftime("%Y%m%d")

    print(f"\n[pykrx] 수집 기간: {from_dt} ~ {to_dt} ({len(tickers)}개 종목)")

    for i, ticker in enumerate(tickers, 1):
        print(f"  [{i:02d}/{len(tickers)}] {ticker} 수집 중...")

        ohlcv_rows = collect_ohlcv(ticker, from_date, to_date)
        fundamental = collect_fundamental(ticker, from_date, to_date)

        # OHLCV + 펀더멘털 병합
        for row in ohlcv_rows:
            fund = fundamental.get(row["date"], {})
            row["per"] = fund.get("per", 0)
            row["pbr"] = fund.get("pbr", 0)
            row["div_yield"] = fund.get("div_yield", 0)

        upsert_rows(ohlcv_rows)
        print(f"     → {len(ohlcv_rows)}개 행 저장 완료")

        # pykrx 서버 과부하 방지
        time.sleep(0.3)

    print(f"\n[pykrx] 전체 수집 완료")


if __name__ == "__main__":
    init_db()
    collect_all(days_back=90)
