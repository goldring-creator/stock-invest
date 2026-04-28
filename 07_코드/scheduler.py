"""
AI 주식 자동화 스케줄러 (오케스트레이터)

실행 방법:
  python3 scheduler.py --phase=collect   # 데이터 수집
  python3 scheduler.py --phase=prepare   # 버핏 분석용 데이터 준비 → company_data.json
  python3 scheduler.py --phase=execute   # guardian_decisions.json 읽어 VTS 주문
  python3 scheduler.py --phase=report    # 일별 리포트 + 텔레그램

원격 에이전트 실행 순서:
  1. collect  → DB에 최신 시세/재무/뉴스 저장
  2. prepare  → company_data.json 생성
  3. [Claude가 company_data.json 읽고 버핏 분석 → guardian_decisions.json 작성]
  4. execute  → guardian_decisions.json 읽어 VTS 주문
  5. report   → 텔레그램 일별 요약
"""
import sys
import argparse
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from database import init_db
from notifier import notify_error
from datetime import date
import traceback


def phase_collect():
    print("\n[scheduler] ▶ Phase: COLLECT")
    from agents.data_agent import run as data_run
    return data_run()


def phase_prepare():
    print("\n[scheduler] ▶ Phase: PREPARE (버핏 분석용 데이터 준비)")
    import prepare_for_guardian
    prepare_for_guardian.main()


def phase_execute():
    print("\n[scheduler] ▶ Phase: EXECUTE (VTS 주문)")
    import execute_trades
    execute_trades.main()


def phase_sell(market: str = "KR"):
    print(f"\n[scheduler] ▶ Phase: SELL ({market})")
    from agents.sell_agent import run as sell_run
    return sell_run(market)


def phase_us_prepare():
    print("\n[scheduler] ▶ Phase: US_PREPARE (미국주식 분석용 데이터 준비)")
    import prepare_us_for_guardian
    prepare_us_for_guardian.main()


def phase_us_execute():
    print("\n[scheduler] ▶ Phase: US_EXECUTE (미국주식 VTS 주문)")
    from agents.us_trading_agent import run as us_run
    return us_run(dry_run=False)


def phase_report():
    print("\n[scheduler] ▶ Phase: REPORT")
    from agents.report_agent import run as report_run
    return report_run()


def main():
    parser = argparse.ArgumentParser(description="AI 주식 자동화 스케줄러")
    parser.add_argument("--phase",
                        choices=["collect", "prepare", "execute", "report",
                                 "sell", "us_prepare", "us_execute"],
                        required=True)
    parser.add_argument("--market", default="KR",
                        choices=["KR", "US", "ALL"],
                        help="sell phase에서 대상 시장 지정")
    args = parser.parse_args()

    init_db()
    print(f"\n{'='*55}")
    print(f"  AI 주식 자동화 — {args.phase.upper()}  {date.today().isoformat()}")
    print(f"{'='*55}")

    try:
        if args.phase == "collect":
            phase_collect()
        elif args.phase == "prepare":
            phase_prepare()
        elif args.phase == "execute":
            phase_execute()
        elif args.phase == "sell":
            phase_sell(args.market)
        elif args.phase == "us_prepare":
            phase_us_prepare()
        elif args.phase == "us_execute":
            phase_us_execute()
        elif args.phase == "report":
            phase_report()
        print(f"\n[scheduler] 완료\n")
    except Exception as e:
        err = traceback.format_exc()
        print(f"[scheduler] ❌ 오류:\n{err}")
        notify_error("Scheduler", f"{args.phase} 오류:\n{str(e)[:300]}")
        sys.exit(1)


if __name__ == "__main__":
    main()
