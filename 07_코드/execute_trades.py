"""
원격 에이전트가 작성한 guardian_decisions.json을 읽어 VTS 주문 실행
"""
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from buffett_guardian.models import GuardianResult
from agents.trading_agent import run as trading_run
from database import init_db, get_conn
from notifier import notify_guardian
from datetime import date

DECISIONS_PATH = Path(__file__).parent.parent / "08_데이터" / "guardian_decisions.json"


def load_decisions() -> list:
    if not DECISIONS_PATH.exists():
        print(f"[execute_trades] guardian_decisions.json 없음: {DECISIONS_PATH}")
        return []
    data = json.loads(DECISIONS_PATH.read_text(encoding="utf-8"))
    results = []
    for d in data:
        r = GuardianResult(
            ticker        = d["ticker"],
            decision      = d["decision"],
            score         = int(d["score"]),
            principles    = d.get("principles", {}),
            reason        = d.get("reason", ""),
            citations     = d.get("citations", []),
            red_flags     = d.get("red_flags", []),
            buffett_quote = d.get("buffett_quote", ""),
        )
        results.append(r)
    return results


def save_to_db(results: list):
    today = date.today().isoformat()
    with get_conn() as conn:
        for r in results:
            conn.execute(
                """INSERT OR REPLACE INTO buffett_decisions
                   (ticker, date, decision, score, reason, citations)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (r.ticker, today, r.decision, r.score, r.reason,
                 json.dumps(r.citations, ensure_ascii=False))
            )


def print_summary(results: list):
    icons = {"APPROVE": "✅", "FLAG": "⚠️", "REJECT": "❌"}
    print(f"\n{'='*55}")
    print(f"  버핏 가디언 판단 결과 ({len(results)}종목)")
    print(f"{'='*55}")
    for r in results:
        icon = icons.get(r.decision, "?")
        print(f"  {icon} {r.ticker}  {r.decision:7}  {r.score}/100점")
        if r.red_flags:
            for rf in r.red_flags[:2]:
                print(f"       ⚠ {rf[:60]}")
    approve = sum(1 for r in results if r.decision == "APPROVE")
    flag    = sum(1 for r in results if r.decision == "FLAG")
    reject  = sum(1 for r in results if r.decision == "REJECT")
    print(f"\n  APPROVE {approve} / FLAG {flag} / REJECT {reject}")
    print(f"{'='*55}\n")


def main():
    init_db()
    results = load_decisions()
    if not results:
        print("[execute_trades] 판단 결과 없음 — 주문 건너뜀")
        return

    print_summary(results)
    save_to_db(results)

    # REJECT/FLAG 텔레그램 알림
    for r in results:
        if r.decision in ("REJECT", "FLAG"):
            notify_guardian(r.ticker, r.ticker, r.decision, r.score, r.reason)

    # 실제 VTS 주문
    trade_results = trading_run(results, dry_run=False)
    print(f"[execute_trades] 주문 완료: {len(trade_results['orders'])}건")


if __name__ == "__main__":
    main()
