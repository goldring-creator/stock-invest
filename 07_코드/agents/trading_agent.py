"""
매매 에이전트
버핏 가디언 결과를 받아 APPROVE/FLAG 종목을 VTS에 자동 주문
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from kis_trader import KisTrader
from kis_client import KisClient
from buffett_guardian.guardian import GuardianResult
from notifier import notify, notify_error
from typing import List
from datetime import date

# 주문 정책
APPROVE_SHARES = 2     # APPROVE: 2주
FLAG_SHARES = 1        # FLAG: 1주
MAX_PRICE_PER_ORDER = 500_000   # 건당 최대 50만원


def _affordable_shares(shares: int, price: int, max_amount: int) -> int:
    """예산 초과 시 주수 조정"""
    while shares > 0 and shares * price > max_amount:
        shares -= 1
    return shares


def run(guardian_results: List[GuardianResult], dry_run: bool = False) -> dict:
    """
    APPROVE/FLAG 종목 자동 매수.
    반환: {"orders": [...], "skipped": [...]}
    """
    trader = KisTrader(dry_run=dry_run)
    client = KisClient()

    orders = []
    skipped = []

    approve_list = [r for r in guardian_results if r.decision == "APPROVE"]
    flag_list    = [r for r in guardian_results if r.decision == "FLAG"]

    targets = [(r, APPROVE_SHARES) for r in approve_list] + \
              [(r, FLAG_SHARES)    for r in flag_list]

    if not targets:
        print("[trading_agent] 매수 대상 없음 (APPROVE/FLAG 없음)")
        return {"orders": [], "skipped": [r.ticker for r in guardian_results]}

    print(f"[trading_agent] 매수 대상: {len(targets)}종목")

    for result, base_shares in targets:
        ticker = result.ticker
        try:
            price_data = client.get_stock_price(ticker)
            price = price_data["price"]
            name  = price_data["name"] or ticker

            shares = _affordable_shares(base_shares, price, MAX_PRICE_PER_ORDER)
            if shares == 0:
                skipped.append(ticker)
                print(f"[trading_agent] {ticker} 건너뜀 (가격 {price:,}원 > 예산)")
                continue

            order_id = trader.buy_market(ticker, shares)
            if order_id:
                orders.append({
                    "ticker": ticker, "name": name,
                    "shares": shares, "price": price,
                    "order_id": order_id, "decision": result.decision,
                })
                print(f"[trading_agent] ✅ {name} {shares}주 주문 ({result.decision})")
            else:
                skipped.append(ticker)

        except Exception as e:
            notify_error("TradingAgent", f"{ticker}: {e}")
            skipped.append(ticker)
            print(f"[trading_agent] ❌ {ticker} 주문 실패: {e}")

    print(f"[trading_agent] 완료: 주문 {len(orders)}건 / 건너뜀 {len(skipped)}건")
    return {"orders": orders, "skipped": skipped}


if __name__ == "__main__":
    from buffett_guardian.guardian import GuardianResult
    # 테스트용 더미 결과
    dummy = [GuardianResult(
        ticker="005930", decision="FLAG", score=65,
        principles={}, reason="테스트", citations=[], red_flags=[], buffett_quote=""
    )]
    run(dummy, dry_run=True)
