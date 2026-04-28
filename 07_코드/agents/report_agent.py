"""
리포트 에이전트
일별 포트폴리오 현황 + 당일 매매 내역을 텔레그램으로 발송
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from kis_trader import KisTrader
from database import get_conn
from notifier import notify, notify_error
from datetime import date


def run() -> bool:
    """일별 성과 리포트 생성 및 텔레그램 발송"""
    today = date.today().isoformat()
    print(f"[report_agent] {today} 리포트 생성...")

    try:
        trader = KisTrader(dry_run=False)
        bal = trader.get_balance()

        # 당일 매매 내역
        with get_conn() as conn:
            trades = conn.execute(
                "SELECT * FROM trade_log WHERE date=? ORDER BY rowid",
                (today,)
            ).fetchall()

        # 포트폴리오 요약
        pnl = bal["total_pnl"]
        pnl_sign = "+" if pnl >= 0 else ""
        pnl_rate = (pnl / bal["total_eval"] * 100) if bal["total_eval"] else 0.0

        holdings_text = ""
        for h in bal["holdings"]:
            sign = "+" if h["pnl"] >= 0 else ""
            holdings_text += (
                f"\n  • {h['name']} {h['quantity']}주  "
                f"평균 {h['avg_price']:,}원  {sign}{h['pnl_rate']:.1f}%"
            )

        # 당일 주문 내역
        trades_text = ""
        for t in trades:
            icon = "📈" if t["order_type"] == "BUY" else "📉"
            trades_text += (
                f"\n  {icon} {t['order_type']} {t['ticker']} "
                f"{t['quantity']}주 @{t['price']:,}원  [{t['status']}]"
            )
        if not trades_text:
            trades_text = "\n  (당일 주문 없음)"

        # 버핏 가디언 당일 판단 요약
        with get_conn() as conn:
            decisions = conn.execute(
                "SELECT ticker, decision, score FROM buffett_decisions WHERE date=?",
                (today,)
            ).fetchall()
        guardian_text = ""
        for d in decisions:
            icon = {"APPROVE": "✅", "FLAG": "⚠️", "REJECT": "❌"}.get(d["decision"], "?")
            guardian_text += f"\n  {icon} {d['ticker']} {d['decision']} {d['score']}점"
        if not guardian_text:
            guardian_text = "\n  (당일 심사 없음)"

        msg = (
            f"📊 <b>일별 성과 리포트</b>  {today}\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"💼 <b>포트폴리오</b>\n"
            f"  예수금:   {bal['cash']:,}원\n"
            f"  평가금액: {bal['total_eval']:,}원\n"
            f"  평가손익: {pnl_sign}{pnl:,}원 ({pnl_sign}{pnl_rate:.2f}%)"
            f"{holdings_text}\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"📋 <b>당일 주문</b>{trades_text}\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"🧠 <b>버핏 가디언 판단</b>{guardian_text}"
        )

        ok = notify(msg)
        if ok:
            print("[report_agent] ✅ 텔레그램 리포트 전송 완료")
        return ok

    except Exception as e:
        notify_error("ReportAgent", str(e))
        print(f"[report_agent] ❌ 리포트 실패: {e}")
        return False


if __name__ == "__main__":
    run()
