"""
전체 시스템 통합 테스트 — 실전 VTS
버핏 가디언 판단 → VTS 실제 주문 → 텔레그램 알림 → DB 저장
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

TICKER = "005930"
COMPANY = {
    "name": "삼성전자",
    "sector": "반도체/전자",
    "per": 12.5, "pbr": 1.1, "roe": 8.2,
    "debt_ratio": 28.0, "revenue_growth": -1.5,
    "operating_margin": 11.4,
    "description": "메모리 반도체 세계 1~2위, HBM3E 양산, 스마트폰 세계 1위",
}

def main():
    init_db()
    print("\n" + "="*58)
    print("  AI 주식 자동화 시스템 — 전체 흐름 (실전 VTS)")
    print("="*58)

    # ── Step 1: 현재 주가 조회 ──────────────────────────────
    print(f"\n[1] {COMPANY['name']} 현재가 조회...")
    client = KisClient()
    price_data = client.get_stock_price(TICKER)
    price = price_data["price"]
    change = price_data["change_rate"]
    print(f"    → {price:,}원  ({change:+.2f}%)")

    # ── Step 2: 버핏 가디언 판단 ────────────────────────────
    print(f"\n[2] 버핏 가디언 심사...")
    guardian = BuffettGuardian()
    result = guardian.analyze(TICKER, COMPANY)

    # ── Step 3: 가디언 결과에 따른 VTS 실제 매수 ────────────
    print(f"\n[3] 매매 결정 (실전 VTS)...")
    trader = KisTrader(dry_run=False)
    order_id = None

    if result.decision == "APPROVE":
        print(f"    → APPROVE ({result.score}/100): 1주 시장가 매수 진행")
        order_id = trader.buy_market(TICKER, 1)
    elif result.decision == "FLAG":
        print(f"    → FLAG ({result.score}/100): 1주 소량 시장가 매수 진행")
        order_id = trader.buy_market(TICKER, 1)
    else:
        print(f"    → REJECT ({result.score}/100): 매수 건너뜀")

    # ── Step 4: 체결 확인 ────────────────────────────────────
    if order_id:
        print(f"\n[4] 체결 확인 (주문번호: {order_id}, 최대 30초)...")
        filled = trader.wait_for_fill(order_id, TICKER, timeout=30, interval=5)
        if filled:
            print("    → ✅ 체결 완료")
        else:
            print("    → ⏳ 미체결 (장 마감 후 또는 지연 — 한투 앱에서 확인)")

    # ── Step 5: 포트폴리오 현황 ─────────────────────────────
    print("\n[5] 포트폴리오 현황 (VTS 실계좌):")
    bal = trader.get_balance()
    trader.print_balance()

    # ── Step 6: 텔레그램 종합 알림 ──────────────────────────
    print("[6] 텔레그램 종합 알림 전송...")

    pnl = bal["total_pnl"]
    pnl_sign = "+" if pnl >= 0 else ""
    holdings_text = ""
    for h in bal["holdings"]:
        sign = "+" if h["pnl"] >= 0 else ""
        holdings_text += f"\n  • {h['name']} {h['quantity']}주  {sign}{h['pnl_rate']:.1f}%"

    guardian_icon = {"APPROVE": "✅", "FLAG": "⚠️", "REJECT": "❌"}.get(result.decision, "?")
    order_text = f"주문번호 {order_id} 접수" if order_id else "매수 없음"

    summary_msg = (
        f"🤖 <b>AI 투자 시스템 실행 완료</b>  {date.today().isoformat()}\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"{guardian_icon} 버핏 판단: <b>{result.decision}</b>  {result.score}/100점\n"
        f"📌 {COMPANY['name']} 현재가: {price:,}원 ({change:+.2f}%)\n"
        f"📋 매매: {order_text}\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"💼 포트폴리오\n"
        f"  예수금: {bal['cash']:,}원\n"
        f"  평가금액: {bal['total_eval']:,}원\n"
        f"  평가손익: {pnl_sign}{pnl:,}원"
        f"{holdings_text}"
    )
    ok = notify(summary_msg)
    print(f"    → {'전송 완료 ✅' if ok else '전송 실패 ❌'}")

    print("\n" + "="*58)
    print("  전체 흐름 테스트 완료")
    print("="*58 + "\n")

if __name__ == "__main__":
    main()
