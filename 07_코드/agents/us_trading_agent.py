"""
미국 주식 매수 에이전트
guardian_decisions_us.json을 읽어 NASD/NYSE에 VTS 주문 실행
"""
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from kis_trader import KisTrader
from notifier import notify_error
from typing import List

DECISIONS_PATH   = Path(__file__).parent.parent.parent / "08_데이터" / "guardian_decisions_us.json"
PRICE_DATA_PATH  = Path(__file__).parent.parent.parent / "08_데이터" / "us_company_data.json"

APPROVE_SHARES = 2
FLAG_SHARES    = 1
MAX_USD_PER_ORDER = 2000.0  # $2,000 per order


def _affordable_shares(shares: int, price_usd: float, max_usd: float) -> int:
    while shares > 0 and shares * price_usd > max_usd:
        shares -= 1
    return shares


def _load_yfinance_prices() -> dict:
    """us_company_data.json에서 yfinance 가격 로드"""
    if not PRICE_DATA_PATH.exists():
        return {}
    data = json.loads(PRICE_DATA_PATH.read_text(encoding="utf-8"))
    return {item["ticker"]: item["price_usd"] for item in data}


def run(dry_run: bool = False) -> dict:
    """guardian_decisions_us.json → VTS 해외주식 주문"""
    if not DECISIONS_PATH.exists():
        print(f"[us_trading] guardian_decisions_us.json 없음: {DECISIONS_PATH}")
        return {"orders": [], "skipped": []}

    decisions = json.loads(DECISIONS_PATH.read_text(encoding="utf-8"))
    trader = KisTrader(dry_run=dry_run)
    yf_prices = _load_yfinance_prices()

    # APPROVE 우선, FLAG 후순위 — 일일 한도(10건) 내에서 고점수 종목 먼저 처리
    buy_decisions = [d for d in decisions if d.get("decision") in ("APPROVE", "FLAG")]
    buy_decisions.sort(key=lambda d: (0 if d["decision"] == "APPROVE" else 1, -d.get("score", 0)))

    remaining = trader.remaining_daily_orders()
    print(f"[us_trading] 오늘 남은 주문 한도: {remaining}건 / 대상 종목: {len(buy_decisions)}건")
    if remaining <= 0:
        print("[us_trading] 일일 주문 한도 소진 — 내일 재시도")
        return {"orders": [], "skipped": [d["ticker"] for d in buy_decisions]}

    orders, skipped = [], []

    for d in buy_decisions:
        ticker   = d["ticker"]
        exchange = d.get("exchange", "NASD")
        base_shares = APPROVE_SHARES if d["decision"] == "APPROVE" else FLAG_SHARES

        try:
            # KIS VTS는 해외주식 현재가 API 미지원 → yfinance 가격 우선 사용
            price_usd = yf_prices.get(ticker, 0)
            if price_usd <= 0:
                price_info = trader.get_overseas_price(ticker, exchange)
                price_usd  = price_info["price_usd"]
            if price_usd <= 0:
                print(f"[us_trading] {ticker} 현재가 조회 실패, 건너뜀")
                skipped.append(ticker)
                continue

            shares = _affordable_shares(base_shares, price_usd, MAX_USD_PER_ORDER)
            if shares == 0:
                print(f"[us_trading] {ticker} 건너뜀 (가격 ${price_usd:.2f} > 예산)")
                skipped.append(ticker)
                continue

            order_id = trader.buy_limit_overseas(ticker, shares, price_usd, exchange)
            if order_id:
                orders.append({
                    "ticker": ticker,
                    "name": d.get("name", ticker),
                    "shares": shares,
                    "price_usd": price_usd,
                    "order_id": order_id,
                    "decision": d["decision"],
                    "exchange": exchange,
                })
                print(f"[us_trading] ✅ {ticker} {shares}주 ${price_usd:.2f} "
                      f"[{exchange}] ({d['decision']})")
            else:
                skipped.append(ticker)

        except Exception as e:
            notify_error("UsTradingAgent", f"{ticker}: {e}")
            skipped.append(ticker)
            print(f"[us_trading] ❌ {ticker} 주문 실패: {e}")

    if skipped:
        print(f"[us_trading] 건너뜀 {len(skipped)}건: {', '.join(skipped)}")
    print(f"[us_trading] 완료: 주문 {len(orders)}건 / 건너뜀 {len(skipped)}건")
    return {"orders": orders, "skipped": skipped}


if __name__ == "__main__":
    run(dry_run=True)
