"""
전체 시스템 통합 테스트 (드라이런)
버핏 가디언 판단 → 조건 통과 시 매수 → 텔레그램 알림 → DB 저장
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from database import init_db
from kis_client import KisClient
from kis_trader import KisTrader
from buffett_guardian.guardian import BuffettGuardian
from notifier import notify, notify_daily_summary
from datetime import date

def main():
    init_db()
    print("\n" + "="*55)
    print("  AI 주식 자동화 시스템 — 전체 흐름 테스트")
    print("="*55)

    # ── Step 1: 현재 주가 조회 ──────────────────────────────
    print("\n[1] 삼성전자 현재가 조회...")
    client = KisClient()
    price_data = client.get_stock_price("005930")
    price = price_data["price"]
    change = price_data["change_rate"]
    print(f"    → {price:,}원  ({change:+.2f}%)")

    # ── Step 2: 버핏 가디언 판단 ────────────────────────────
    print("\n[2] 버핏 가디언 심사...")
    guardian = BuffettGuardian()
    result = guardian.analyze("005930", {
        "name": "삼성전자",
        "sector": "반도체/전자",
        "per": 12.5, "pbr": 1.1, "roe": 8.2,
        "debt_ratio": 28.0, "revenue_growth": -1.5,
        "operating_margin": 11.4,
        "description": "메모리 반도체 세계 1~2위, HBM3E 양산, 스마트폰 세계 1위",
    })

    # ── Step 3: 가디언 통과 시 매수 ─────────────────────────
    print(f"\n[3] 매매 결정 (드라이런)...")
    trader = KisTrader(dry_run=True)

    if result.decision == "APPROVE":
        shares = min(3, 1_000_000 // price)   # 최대 100만원 이내
        order_id = trader.buy("005930", shares, price)
        print(f"    → APPROVE: {shares}주 매수 주문 접수 ({order_id})")
    elif result.decision == "FLAG":
        shares = 1   # FLAG면 1주만 시험 매수
        order_id = trader.buy("005930", shares, price)
        print(f"    → FLAG: 1주 소량 매수 ({order_id})")
    else:
        print(f"    → REJECT: 매수 건너뜀")
        order_id = None

    # ── Step 4: 포트폴리오 현황 ─────────────────────────────
    print("\n[4] 포트폴리오 현황 (드라이런 기준):")
    trader.print_balance()

    # ── Step 5: 텔레그램 일별 요약 알림 ─────────────────────
    print("[5] 텔레그램 일별 요약 알림...")
    notify_daily_summary(
        date=date.today().isoformat(),
        portfolio_value=100_000_000,
        daily_pnl=0,
        daily_pnl_rate=0.0,
    )
    notify(f"🤖 시스템 정상 작동 확인\n버핏 판단: {result.decision} ({result.score}/100)\n삼성전자 현재가: {price:,}원")
    print("    → 텔레그램 전송 완료")

    print("\n" + "="*55)
    print("  ✅ 전체 흐름 테스트 완료")
    print("  ※ 드라이런 — 실제 주문 없음, DB·알림만 발생")
    print("="*55 + "\n")

if __name__ == "__main__":
    main()
