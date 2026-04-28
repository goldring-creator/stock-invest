"""
버핏 가디언 분석 준비 스크립트
DB에서 최신 재무데이터를 읽어 company_data.json 출력
→ 원격 에이전트(Claude)가 이 파일을 읽고 직접 버핏 분석 수행
"""
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from database import init_db, get_conn

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

COMPANY_META = {
    "005930": {"name": "삼성전자",  "sector": "반도체/전자",
               "description": "메모리 반도체 세계 1~2위, HBM3E 양산, 스마트폰 세계 1위"},
    "000660": {"name": "SK하이닉스","sector": "반도체",
               "description": "HBM 세계 1위, AI 서버용 메모리 핵심 공급사"},
    "035420": {"name": "NAVER",     "sector": "인터넷/플랫폼",
               "description": "국내 검색 독점, 라인 글로벌, 클라우드/커머스 확장"},
    "005380": {"name": "현대차",    "sector": "자동차",
               "description": "글로벌 3위 완성차, EV 전환 가속, 제네시스 프리미엄"},
    "051910": {"name": "LG화학",    "sector": "화학/배터리",
               "description": "배터리 소재 세계 1위, LG에너지솔루션 지분 보유"},
    "006400": {"name": "삼성SDI",   "sector": "배터리",
               "description": "전기차 배터리, ESS, 소형전지 글로벌 공급"},
    "035720": {"name": "카카오",    "sector": "플랫폼",
               "description": "국내 메신저 독점, 카카오페이/뱅크/엔터 생태계"},
    "000270": {"name": "기아",      "sector": "자동차",
               "description": "EV 전환 선도, 미국/유럽 시장 확대, PBV 신사업"},
    "105560": {"name": "KB금융",    "sector": "금융",
               "description": "국내 최대 금융지주, 안정적 배당, ROE 10%대"},
    "055550": {"name": "신한지주",  "sector": "금융",
               "description": "글로벌 진출 금융지주, 아시아 네트워크 강점"},
}

OUTPUT_PATH = Path(__file__).parent.parent / "08_데이터" / "company_data.json"


def load_financials(ticker: str, conn) -> dict:
    row = conn.execute(
        "SELECT per, pbr, close FROM daily_price WHERE ticker=? ORDER BY date DESC LIMIT 1",
        (ticker,)
    ).fetchone()

    fins = conn.execute(
        "SELECT account_nm, amount FROM financial_statement WHERE ticker=? ORDER BY period DESC LIMIT 30",
        (ticker,)
    ).fetchall()

    per  = float(row["per"]   or 0) if row else 0.0
    pbr  = float(row["pbr"]   or 0) if row else 0.0
    price = int(row["close"]  or 0) if row else 0

    fm = {r["account_nm"]: r["amount"] for r in fins} if fins else {}
    revenue    = fm.get("매출액", 0) or 0
    op_income  = fm.get("영업이익", 0) or 0
    net_income = fm.get("당기순이익", 0) or 0
    equity     = fm.get("자본총계", 1) or 1
    debt       = fm.get("부채총계", 0) or 0

    roe        = round(net_income / equity * 100, 1) if equity else 0.0
    op_margin  = round(op_income / revenue * 100, 1) if revenue else 0.0
    debt_ratio = round(debt / equity * 100, 1) if equity else 0.0

    # 뉴스 감성점수 평균
    news = conn.execute(
        "SELECT AVG(sentiment_score) as avg FROM news_sentiment WHERE ticker=? ORDER BY date DESC LIMIT 5",
        (ticker,)
    ).fetchone()
    sentiment = round(float(news["avg"] or 0), 2) if news else 0.0

    return {
        "per": per, "pbr": pbr, "price": price,
        "roe": roe, "operating_margin": op_margin,
        "debt_ratio": debt_ratio, "sentiment": sentiment,
        "revenue_growth": 0.0,
    }


def main():
    init_db()
    companies = []
    with get_conn() as conn:
        for ticker in WATCH_TICKERS:
            meta = COMPANY_META.get(ticker, {"name": ticker, "sector": "기타", "description": ""})
            fin  = load_financials(ticker, conn)
            companies.append({"ticker": ticker, **meta, **fin})

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(companies, ensure_ascii=False, indent=2))
    print(f"[prepare] company_data.json 생성 완료 ({len(companies)}종목)")
    print(f"[prepare] 경로: {OUTPUT_PATH}")

    # 간단 미리보기
    for c in companies:
        print(f"  {c['ticker']} {c['name']:8} PER={c['per']:.1f} ROE={c['roe']:.1f}% "
              f"부채={c['debt_ratio']:.0f}%")


if __name__ == "__main__":
    main()
