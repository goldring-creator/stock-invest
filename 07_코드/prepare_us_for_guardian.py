"""
미국 주식 버핏 분석 준비 스크립트
yfinance로 재무데이터 수집 → us_company_data.json 출력
→ 원격 에이전트(Claude)가 읽고 직접 버핏 분석 수행
"""
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

OUTPUT_PATH = Path(__file__).parent.parent / "08_데이터" / "us_company_data.json"

# 미국 감시 종목 (전략 가이드 기반)
US_WATCHLIST = [
    {"ticker": "QQQ",  "exchange": "NASD", "name": "Invesco QQQ Trust",
     "sector": "ETF/기술", "description": "NASDAQ-100 추종 ETF. AI·반도체 사상 최고치 경신 중."},
    {"ticker": "XLK",  "exchange": "NYSE", "name": "Technology Select Sector SPDR",
     "sector": "ETF/기술", "description": "S&P500 기술섹터 ETF. AI 인프라 수요로 강세."},
    {"ticker": "XLE",  "exchange": "NYSE", "name": "Energy Select Sector SPDR",
     "sector": "ETF/에너지", "description": "에너지 섹터 ETF. 유가 $107 급등, 호르무즈 봉쇄 수혜."},
    {"ticker": "ITA",  "exchange": "NYSE", "name": "iShares U.S. Aerospace & Defense ETF",
     "sector": "ETF/방산", "description": "미국 방산 ETF. 지정학적 긴장 고조, 국방 예산 증가 수혜."},
    {"ticker": "GLD",  "exchange": "NYSE", "name": "SPDR Gold Shares",
     "sector": "ETF/금", "description": "금 현물 ETF. 금 $4,719/oz 사상 최고. 안전자산 수요."},
    {"ticker": "NVDA", "exchange": "NASD", "name": "NVIDIA Corporation",
     "sector": "반도체/AI", "description": "AI 가속기 시장 점유율 80%+. Vera Rubin 아키텍처 출시 예정. 데이터센터 수요 폭증."},
    {"ticker": "AAPL", "exchange": "NASD", "name": "Apple Inc.",
     "sector": "기술/소비자", "description": "시가총액 세계 1위. Apple Intelligence AI 서비스 확대. 안정적 생태계 수익."},
    {"ticker": "MSFT", "exchange": "NASD", "name": "Microsoft Corporation",
     "sector": "기술/클라우드", "description": "Azure 클라우드 AI 매출 급증. OpenAI 투자 수혜. 엔터프라이즈 AI 1위."},
]


def fetch_financials(ticker: str) -> dict:
    """yfinance로 재무 데이터 수집"""
    try:
        import yfinance as yf
        info = yf.Ticker(ticker).info
        return {
            "per": round(float(info.get("trailingPE") or 0), 1),
            "pbr": round(float(info.get("priceToBook") or 0), 1),
            "price_usd": round(float(info.get("regularMarketPrice") or
                                     info.get("previousClose") or 0), 2),
            "roe": round(float(info.get("returnOnEquity") or 0) * 100, 1),
            "operating_margin": round(float(info.get("operatingMargins") or 0) * 100, 1),
            "debt_ratio": round(float(info.get("debtToEquity") or 0), 1),
            "revenue_growth": round(float(info.get("revenueGrowth") or 0) * 100, 1),
            "market_cap_b": round(float(info.get("marketCap") or 0) / 1e9, 1),
            "52w_high": round(float(info.get("fiftyTwoWeekHigh") or 0), 2),
            "52w_low": round(float(info.get("fiftyTwoWeekLow") or 0), 2),
            "sentiment": 0.0,
        }
    except Exception as e:
        print(f"  [준비] {ticker} yfinance 실패: {e}")
        return {
            "per": 0, "pbr": 0, "price_usd": 0,
            "roe": 0, "operating_margin": 0, "debt_ratio": 0,
            "revenue_growth": 0, "market_cap_b": 0,
            "52w_high": 0, "52w_low": 0, "sentiment": 0.0,
        }


def fetch_price_from_kis(ticker: str, exchange: str) -> float:
    """KIS 해외주식 현재가 조회 (yfinance 실패 시 대체)"""
    try:
        from kis_trader import KisTrader
        trader = KisTrader(dry_run=True)
        info = trader.get_overseas_price(ticker, exchange)
        return info.get("price_usd", 0)
    except Exception:
        return 0


def main():
    companies = []
    for stock in US_WATCHLIST:
        ticker = stock["ticker"]
        print(f"  수집 중: {ticker} ({stock['name']})")
        fins = fetch_financials(ticker)

        # yfinance 가격 실패 시 KIS API 대체
        if fins["price_usd"] <= 0:
            fins["price_usd"] = fetch_price_from_kis(ticker, stock["exchange"])

        companies.append({**stock, **fins})
        print(f"    → ${fins['price_usd']:.2f}  PER={fins['per']}  ROE={fins['roe']}%")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(companies, ensure_ascii=False, indent=2))
    print(f"\n[us_prepare] us_company_data.json 생성 완료 ({len(companies)}종목)")
    print(f"[us_prepare] 경로: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
