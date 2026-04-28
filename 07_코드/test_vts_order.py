"""
VTS 실제 주문 테스트 (모의투자)
잔고조회 → 매수가능조회 → 삼성전자 1주 시장가 매수 → 체결 확인
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from database import init_db
from kis_client import KisClient
from kis_trader import KisTrader

def main():
    init_db()
    print("\n" + "="*55)
    print("  VTS 실제 주문 테스트 (모의투자)")
    print("="*55)

    client = KisClient()

    # ── Step 1: 현재가 조회 ──────────────────────────────────
    print("\n[1] 삼성전자 현재가 조회...")
    price_data = client.get_stock_price("005930")
    price = price_data["price"]
    name  = price_data["name"]
    print(f"    → {name}: {price:,}원  ({price_data['change_rate']:+.2f}%)")

    # ── Step 2: 잔고 조회 ────────────────────────────────────
    print("\n[2] 모의투자 잔고 조회...")
    trader = KisTrader(dry_run=False)
    trader.print_balance()

    # ── Step 3: 시장가 매수 주문 ─────────────────────────────
    print("[3] 삼성전자 1주 시장가 매수 주문...")
    confirm = input("    실제 VTS 주문을 진행하시겠습니까? (y/N): ").strip().lower()
    if confirm != "y":
        print("    → 취소됨")
        return

    order_id = trader.buy_market("005930", 1)
    if order_id:
        print(f"    → 주문번호: {order_id}")

        # ── Step 4: 체결 대기 ───────────────────────────────
        print("\n[4] 체결 확인 (최대 60초)...")
        filled = trader.wait_for_fill(order_id, "005930", timeout=60, interval=5)
        if filled:
            print("    → 체결 완료!")
        else:
            print("    → 체결 대기 중 (장 마감이거나 지연될 수 있음)")

        # ── Step 5: 잔고 재조회 ─────────────────────────────
        print("\n[5] 주문 후 잔고:")
        trader.print_balance()
    else:
        print("    → 주문 실패")

    print("="*55 + "\n")

if __name__ == "__main__":
    main()
