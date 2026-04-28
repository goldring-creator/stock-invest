"""
버핏 가디언 에이전트
DB에서 최신 재무지표를 읽어 각 종목을 분석하고 APPROVE/FLAG/REJECT 판단
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from buffett_guardian.guardian import BuffettGuardian, GuardianResult
from database import get_conn
from notifier import notify_error
from typing import List
from datetime import date

WATCH_TICKERS = [
    "005930",  # 삼성전자
    "000660",  # SK하이닉스
    "035420",  # NAVER
    "005380",  # 현대차
    "051910",  # LG화학
    "006400",  # 삼성SDI
    "035720",  # 카카오
    "000270",  # 기아
    "105560",  # KB금융
    "055550",  # 신한지주
]

# 수동 보완 정보 (DART로 자동화 전까지)
COMPANY_META = {
    "005930": {"name": "삼성전자", "sector": "반도체/전자",
               "description": "메모리 반도체 세계 1~2위, HBM3E 양산, 스마트폰 세계 1위"},
    "000660": {"name": "SK하이닉스", "sector": "반도체",
               "description": "HBM 세계 1위, AI 서버용 메모리 핵심 공급사"},
    "035420": {"name": "NAVER", "sector": "인터넷/플랫폼",
               "description": "국내 검색 독점, 라인 글로벌, 클라우드/커머스 확장"},
    "005380": {"name": "현대차", "sector": "자동차",
               "description": "글로벌 3위 완성차, EV 전환 가속, 제네시스 프리미엄"},
    "051910": {"name": "LG화학", "sector": "화학/배터리",
               "description": "배터리 소재 세계 1위, LG에너지솔루션 지분 보유"},
    "006400": {"name": "삼성SDI", "sector": "배터리",
               "description": "전기차 배터리, ESS, 소형전지 글로벌 공급"},
    "035720": {"name": "카카오", "sector": "플랫폼",
               "description": "국내 메신저 독점, 카카오페이/뱅크/엔터 생태계"},
    "000270": {"name": "기아", "sector": "자동차",
               "description": "EV 전환 선도, 미국/유럽 시장 확대, PBV 신사업"},
    "105560": {"name": "KB금융", "sector": "금융",
               "description": "국내 최대 금융지주, 안정적 배당, ROE 10%대"},
    "055550": {"name": "신한지주", "sector": "금융",
               "description": "글로벌 진출 금융지주, 아시아 네트워크 강점"},
}


def _load_financials(ticker: str) -> dict:
    """DB에서 최신 재무지표 로드. 없으면 기본값 반환."""
    with get_conn() as conn:
        # 최신 PER/PBR/ROE (daily_price 테이블)
        row = conn.execute(
            "SELECT per, pbr FROM daily_price WHERE ticker=? ORDER BY date DESC LIMIT 1",
            (ticker,)
        ).fetchone()

        # 최신 재무제표 (financial_statement 테이블)
        fin = conn.execute(
            """SELECT account_nm, amount FROM financial_statement
               WHERE ticker=? ORDER BY period DESC LIMIT 20""",
            (ticker,)
        ).fetchall()

    per = row["per"] if row and row["per"] else 0.0
    pbr = row["pbr"] if row and row["pbr"] else 0.0

    # 재무항목 파싱
    fin_map = {r["account_nm"]: r["amount"] for r in fin} if fin else {}
    revenue = fin_map.get("매출액", 0)
    op_income = fin_map.get("영업이익", 0)
    total_equity = fin_map.get("자본총계", 1)
    total_debt = fin_map.get("부채총계", 0)

    roe = (fin_map.get("당기순이익", 0) / total_equity * 100) if total_equity else 0.0
    op_margin = (op_income / revenue * 100) if revenue else 0.0
    debt_ratio = (total_debt / total_equity * 100) if total_equity else 0.0

    return {
        "per": round(per, 1),
        "pbr": round(pbr, 2),
        "roe": round(roe, 1),
        "operating_margin": round(op_margin, 1),
        "debt_ratio": round(debt_ratio, 1),
        "revenue_growth": 0.0,  # TODO: 전기 대비 성장률 계산
    }


def run(tickers: list = None) -> List[GuardianResult]:
    """
    종목 리스트를 버핏 원칙으로 심사.
    반환: GuardianResult 리스트 (APPROVE/FLAG/REJECT 포함)
    """
    tickers = tickers or WATCH_TICKERS
    guardian = BuffettGuardian()
    results = []

    print(f"[guardian_agent] {len(tickers)}종목 심사 시작")

    for ticker in tickers:
        try:
            meta = COMPANY_META.get(ticker, {"name": ticker, "sector": "기타",
                                             "description": ""})
            financials = _load_financials(ticker)
            company_info = {**meta, **financials}

            result = guardian.analyze(ticker, company_info)
            results.append(result)
        except Exception as e:
            notify_error("GuardianAgent", f"{ticker}: {e}")
            print(f"[guardian_agent] ❌ {ticker} 분석 실패: {e}")

    approve = [r for r in results if r.decision == "APPROVE"]
    flag = [r for r in results if r.decision == "FLAG"]
    reject = [r for r in results if r.decision == "REJECT"]
    print(f"[guardian_agent] 결과: APPROVE {len(approve)} / FLAG {len(flag)} / REJECT {len(reject)}")

    return results


if __name__ == "__main__":
    results = run(["005930", "000660"])
    for r in results:
        print(f"  {r.ticker}: {r.decision} ({r.score}점)")
