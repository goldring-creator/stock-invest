"""
AI 주식 자동매매 CLI
scheduler.py 위에 올라가는 사용자 친화적 인터페이스.
기존 scheduler.py는 그대로 유지되며, 이 파일은 래퍼 역할만 합니다.

사용법:
  python3 cli.py collect              # 시세·재무·뉴스 수집
  python3 cli.py prepare              # 국내 버핏 분석 데이터 준비
  python3 cli.py us-prepare           # 미국 버핏 분석 데이터 준비
  python3 cli.py execute              # 국내 주문 실행
  python3 cli.py us-execute           # 미국 주문 실행
  python3 cli.py sell                 # 국내 매도 체크
  python3 cli.py sell --market US     # 미국 매도 체크
  python3 cli.py sell --market ALL    # 전체 매도 체크
  python3 cli.py report               # 일별 리포트 (콘솔)
  python3 cli.py status               # API 연결 상태 확인
"""
import sys
import subprocess
from pathlib import Path
from datetime import date

CODE_DIR = Path(__file__).parent
sys.path.insert(0, str(CODE_DIR))

BANNER = r"""
  ╔══════════════════════════════════════════╗
  ║   AI 주식 자동매매  ·  모의투자 시스템   ║
  ╚══════════════════════════════════════════╝"""

COMMANDS = {
    "collect":    ("시세·재무·뉴스 수집",          "--phase=collect"),
    "prepare":    ("국내 버핏 분석 데이터 준비",     "--phase=prepare"),
    "us-prepare": ("미국 버핏 분석 데이터 준비",     "--phase=us_prepare"),
    "execute":    ("국내 VTS 주문 실행",             "--phase=execute"),
    "us-execute": ("미국 VTS 주문 실행",             "--phase=us_execute"),
    "report":     ("일별 포트폴리오 리포트",          "--phase=report"),
}


def print_banner():
    print(BANNER)
    print(f"  날짜: {date.today().isoformat()}\n")


def print_help():
    print_banner()
    print("  사용법: python3 cli.py <명령어> [옵션]\n")
    print("  ┌─────────────┬────────────────────────────────┐")
    print("  │ 명령어      │ 설명                           │")
    print("  ├─────────────┼────────────────────────────────┤")
    for cmd, (desc, _) in COMMANDS.items():
        print(f"  │ {cmd:<11}  │ {desc:<30} │")
    print("  │ sell        │ 매도 체크  [--market KR/US/ALL]│")
    print("  │ status      │ API 연결 상태 확인             │")
    print("  └─────────────┴────────────────────────────────┘")
    print()


def run_phase(phase_flag: str, market: str = None):
    scheduler = CODE_DIR / "scheduler.py"
    cmd = [sys.executable, str(scheduler), phase_flag]
    if market:
        cmd += ["--market", market]
    result = subprocess.run(cmd, cwd=str(CODE_DIR))
    return result.returncode


def cmd_sell(market: str):
    valid = {"KR", "US", "ALL"}
    if market.upper() not in valid:
        print(f"  오류: --market 값은 KR, US, ALL 중 하나여야 합니다. (입력: {market})")
        sys.exit(1)
    return run_phase("--phase=sell", market.upper())


def cmd_status():
    print_banner()
    print("  [status] API 연결 상태 확인 중...\n")
    try:
        from config_loader import get_kis_config, get_telegram_config, get_dart_config
        kis = get_kis_config()
        tg = get_telegram_config()
        dart = get_dart_config()

        def ok_str(val): return "✓ 설정됨" if val else "✗ 미설정"

        print(f"  KIS 앱키     : {ok_str(kis.get('app_key'))}")
        print(f"  KIS 앱시크릿 : {ok_str(kis.get('app_secret'))}")
        print(f"  KIS 계좌번호 : {ok_str(kis.get('account_no'))}")
        print(f"  모의투자 모드: {'✓ 활성화' if kis.get('use_mock', True) else '△ 실전'}")
        print(f"  DART API키   : {ok_str(dart.get('api_key'))}")
        print(f"  Telegram 봇  : {ok_str(tg.get('bot_token'))}")
        print(f"  Telegram ID  : {ok_str(tg.get('chat_id'))}")
        print()

        from kis_auth import get_access_token
        token = get_access_token()
        if token:
            print("  KIS 액세스 토큰: ✓ 발급 성공")
        else:
            print("  KIS 액세스 토큰: ✗ 발급 실패 — 앱키/시크릿을 확인하세요")
    except Exception as e:
        print(f"  오류: {e}")
        print("  config.yaml 파일이 06_설정파일/ 에 있는지 확인하세요.")
        return 1
    return 0


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help", "help"):
        print_help()
        sys.exit(0)

    print_banner()
    cmd = sys.argv[1].lower()

    if cmd == "status":
        sys.exit(cmd_status())

    if cmd == "sell":
        market = "KR"
        for i, arg in enumerate(sys.argv[2:], 2):
            if arg == "--market" and i + 1 < len(sys.argv):
                market = sys.argv[i + 1]
        sys.exit(cmd_sell(market))

    if cmd in COMMANDS:
        desc, flag = COMMANDS[cmd]
        print(f"  실행: {desc}\n")
        rc = run_phase(flag)
        sys.exit(rc)

    print(f"  알 수 없는 명령어: {cmd}")
    print("  python3 cli.py --help 로 사용법을 확인하세요.")
    sys.exit(1)


if __name__ == "__main__":
    main()
