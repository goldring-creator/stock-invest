"""
데이터 수집 에이전트
pykrx OHLCV + DART 재무제표 + 네이버 뉴스 감성점수를 수집해 DB에 저장
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from data_pipeline.pykrx_collector import collect_all as collect_price
from data_pipeline.dart_collector import collect_all as collect_dart
from data_pipeline.news_collector import collect_news_sentiment
from notifier import notify_error
from datetime import date

WATCH_TICKERS = [
    "005930",  # 삼성전자
    "000660",  # SK하이닉스
    "035420",  # NAVER
    "005380",  # 현대차
    "051910",  # LG화학
    "006400",  # 삼성SDI
    "035720",  # 카카오
    "000270",  # 기아
    "105560",  # KB금융
    "055550",  # 신한지주
]


def run(tickers: list = None) -> dict:
    """
    전체 데이터 수집 실행.
    반환: {"price": bool, "dart": bool, "news": bool}
    """
    tickers = tickers or WATCH_TICKERS
    today = date.today().isoformat()
    results = {}

    print(f"[data_agent] {today} 데이터 수집 시작 ({len(tickers)}종목)")

    # ── 주가/재무지표 수집 (pykrx) ──────────────────────────
    try:
        collect_price(tickers)
        results["price"] = True
        print("[data_agent] ✅ 주가/PER/PBR 수집 완료")
    except Exception as e:
        notify_error("DataAgent.price", str(e))
        results["price"] = False
        print(f"[data_agent] ❌ 주가 수집 실패: {e}")

    # ── DART 재무제표 수집 ───────────────────────────────────
    try:
        collect_dart(tickers)
        results["dart"] = True
        print("[data_agent] ✅ DART 재무제표 수집 완료")
    except Exception as e:
        notify_error("DataAgent.dart", str(e))
        results["dart"] = False
        print(f"[data_agent] ❌ DART 수집 실패: {e}")

    # ── 뉴스 감성점수 수집 ───────────────────────────────────
    try:
        collect_news_sentiment(tickers)
        results["news"] = True
        print("[data_agent] ✅ 뉴스 감성점수 수집 완료")
    except Exception as e:
        notify_error("DataAgent.news", str(e))
        results["news"] = False
        print(f"[data_agent] ❌ 뉴스 수집 실패: {e}")

    success = sum(results.values())
    print(f"[data_agent] 수집 완료: {success}/3 성공")
    return results


if __name__ == "__main__":
    run()
