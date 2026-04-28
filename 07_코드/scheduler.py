"""
AI 주식 자동화 스케줄러 (오케스트레이터)

실행 방법:
  python3 scheduler.py --phase=collect   # 08:30 데이터 수집
  python3 scheduler.py --phase=trade     # 09:00 분석 + 주문
  python3 scheduler.py --phase=report    # 15:30 일별 리포트
  python3 scheduler.py --phase=all       # 전체 순서대로 실행 (테스트용)

crontab 등록 (Mac 로컬):
  30 8  * * 1-5  cd [경로] && python3 scheduler.py --phase=collect
  00 9  * * 1-5  cd [경로] && python3 scheduler.py --phase=trade
  30 15 * * 1-5  cd [경로] && python3 scheduler.py --phase=report

GitHub Actions: .github/workflows/trading.yml 참조
"""
import sys
import argparse
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from database import init_db
from notifier import notify, notify_error
from datetime import date
import traceback


def phase_collect():
    """08:30 — 데이터 수집"""
    print("\n[scheduler] ▶ Phase: COLLECT")
    from agents.data_agent import run as data_run
    results = data_run()
    ok = sum(results.values())
    notify(f"📥 <b>데이터 수집 완료</b>  {date.today().isoformat()}\n"
           f"주가/PER {'✅' if results.get('price') else '❌'}  "
           f"재무제표 {'✅' if results.get('dart') else '❌'}  "
           f"뉴스감성 {'✅' if results.get('news') else '❌'}\n"
           f"({ok}/3 성공)")
    return results


def phase_trade(dry_run: bool = False):
    """09:00 — 버핏 심사 + 자동 주문"""
    print("\n[scheduler] ▶ Phase: TRADE")
    from agents.guardian_agent import run as guardian_run, WATCH_TICKERS
    from agents.trading_agent import run as trading_run

    guardian_results = guardian_run(WATCH_TICKERS)
    trade_results = trading_run(guardian_results, dry_run=dry_run)
    return {"guardian": guardian_results, "trades": trade_results}


def phase_report():
    """15:30 — 일별 리포트"""
    print("\n[scheduler] ▶ Phase: REPORT")
    from agents.report_agent import run as report_run
    return report_run()


def main():
    parser = argparse.ArgumentParser(description="AI 주식 자동화 스케줄러")
    parser.add_argument("--phase", choices=["collect", "trade", "report", "all"],
                        required=True, help="실행할 단계")
    parser.add_argument("--dry-run", action="store_true",
                        help="드라이런 모드 (실제 주문 없음)")
    args = parser.parse_args()

    init_db()
    print(f"\n{'='*55}")
    print(f"  AI 주식 자동화 — {args.phase.upper()}  {date.today().isoformat()}")
    print(f"{'='*55}")

    try:
        if args.phase == "collect":
            phase_collect()
        elif args.phase == "trade":
            phase_trade(dry_run=args.dry_run)
        elif args.phase == "report":
            phase_report()
        elif args.phase == "all":
            phase_collect()
            phase_trade(dry_run=args.dry_run)
            phase_report()
        print(f"\n[scheduler] 완료\n")

    except Exception as e:
        err = traceback.format_exc()
        print(f"[scheduler] ❌ 오류:\n{err}")
        notify_error("Scheduler", f"{args.phase} 단계 오류:\n{str(e)[:300]}")
        sys.exit(1)


if __name__ == "__main__":
    main()
