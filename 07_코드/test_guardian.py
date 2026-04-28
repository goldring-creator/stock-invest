"""
버핏 가디언 에이전트 테스트
실행: python test_guardian.py

삼성전자(005930) — APPROVE 기대
카카오(035720)   — FLAG 또는 REJECT 기대
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from database import init_db
from buffett_guardian.guardian import BuffettGuardian


TEST_STOCKS = [
    {
        "ticker": "005930",
        "info": {
            "name": "삼성전자",
            "sector": "반도체/전자",
            "per": 12.5,
            "pbr": 1.1,
            "roe": 8.2,
            "debt_ratio": 28.0,
            "revenue_growth": -1.5,
            "operating_margin": 11.4,
            "description": (
                "메모리 반도체(DRAM·NAND) 세계 1~2위, 스마트폰 세계 1위. "
                "HBM3E 양산 개시, AI 반도체 수요 수혜 기대. "
                "강력한 브랜드와 수직계열화된 공급망 보유. "
                "50년 이상 지속 성장한 한국 대표 제조 기업."
            ),
        }
    },
    {
        "ticker": "035720",
        "info": {
            "name": "카카오",
            "sector": "인터넷/플랫폼",
            "per": 42.0,
            "pbr": 1.8,
            "roe": 4.1,
            "debt_ratio": 120.0,
            "revenue_growth": 5.2,
            "operating_margin": 3.8,
            "description": (
                "국내 메신저 카카오톡 독점적 지위. "
                "카카오페이·카카오뱅크·카카오엔터 등 문어발 확장. "
                "SM엔터 인수 과정 주가조작 혐의 검찰 수사 진행 중. "
                "영업이익률 지속 하락, 부채비율 급증."
            ),
        }
    },
]


def main():
    init_db()
    guardian = BuffettGuardian()

    results = []
    for stock in TEST_STOCKS:
        result = guardian.analyze(stock["ticker"], stock["info"])
        results.append(result)

    print("\n" + "="*55)
    print("  버핏 가디언 심사 결과 요약")
    print("="*55)
    icons = {"APPROVE": "✅", "FLAG": "⚠️", "REJECT": "❌"}
    for r in results:
        icon = icons.get(r.decision, "?")
        print(f"  {icon} {r.ticker:8} {r.decision:8} {r.score:3}/100")
    print("="*55)
    print("\n  DB에 판단 이력이 저장됐습니다.")


if __name__ == "__main__":
    main()
