"""
네이버 뉴스 수집 + Claude Haiku 감성 분석
실행: python news_collector.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import requests
import time
from datetime import date
from typing import List, Optional
import anthropic

from config_loader import get_naver_config, get_claude_config
from database import get_conn, init_db


TICKER_TO_NAME = {
    "005930": "삼성전자",
    "000660": "SK하이닉스",
    "005380": "현대차",
    "035420": "NAVER",
    "051910": "LG화학",
    "006400": "삼성SDI",
    "028260": "삼성물산",
    "012330": "현대모비스",
    "066570": "LG전자",
    "003550": "LG그룹",
    "017670": "SK텔레콤",
    "086790": "하나금융",
    "105560": "KB금융",
    "055550": "신한금융",
    "000270": "기아자동차",
}

SENTIMENT_PROMPT = """당신은 주식 투자 전문 애널리스트입니다.
아래 뉴스 제목을 읽고, 해당 종목 주가에 미치는 영향을 분석하세요.

뉴스 제목: {title}
관련 종목: {company}

다음 형식으로만 답하세요 (JSON):
{{"score": <-1.0~1.0 실수>, "summary": "<한 줄 요약 (30자 이내)>"}}

score 기준:
 1.0 = 매우 긍정 (실적 대폭 개선, 대형 계약, 기술 혁신)
 0.5 = 긍정 (실적 소폭 개선, 신제품 출시)
 0.0 = 중립 (일반 소식, 영향 불명확)
-0.5 = 부정 (실적 저하, 소송, 규제)
-1.0 = 매우 부정 (대형 사고, 파산 위기, 대규모 제재)"""


class NaverNewsCollector:
    SEARCH_URL = "https://openapi.naver.com/v1/search/news.json"

    def __init__(self):
        naver = get_naver_config()
        self.headers = {
            "X-Naver-Client-Id": naver["client_id"],
            "X-Naver-Client-Secret": naver["client_secret"],
        }

    def fetch_news(self, company_name: str, count: int = 10) -> List[dict]:
        try:
            resp = requests.get(
                self.SEARCH_URL,
                headers=self.headers,
                params={
                    "query": f"{company_name} 주가 실적",
                    "display": count,
                    "sort": "date",
                },
                timeout=10,
            )
            resp.raise_for_status()
            items = resp.json().get("items", [])
            return [
                {
                    "title": item["title"].replace("<b>", "").replace("</b>", ""),
                    "url": item.get("originallink") or item.get("link", ""),
                    "pub_date": item.get("pubDate", ""),
                }
                for item in items
            ]
        except Exception as e:
            print(f"  [Naver] 뉴스 수집 오류 ({company_name}): {e}")
            return []


class SentimentAnalyzer:
    def __init__(self):
        claude_cfg = get_claude_config()
        self.client = anthropic.Anthropic(api_key=claude_cfg["api_key"])

    def analyze(self, title: str, company: str) -> Optional[dict]:
        try:
            msg = self.client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=100,
                messages=[{
                    "role": "user",
                    "content": SENTIMENT_PROMPT.format(title=title, company=company)
                }]
            )
            import json
            text = msg.content[0].text.strip()
            # JSON 블록만 추출
            if "```" in text:
                text = text.split("```")[1].replace("json", "").strip()
            return json.loads(text)
        except Exception as e:
            print(f"  [Claude] 감성 분석 오류: {e}")
            return None


def collect_all(tickers: List[str] = None, news_per_ticker: int = 5):
    if tickers is None:
        tickers = list(TICKER_TO_NAME.keys())

    news_client = NaverNewsCollector()
    sentiment = SentimentAnalyzer()
    today = date.today().strftime("%Y-%m-%d")

    print(f"\n[뉴스] {len(tickers)}개 종목 뉴스 수집 시작")

    with get_conn() as conn:
        for ticker in tickers:
            company = TICKER_TO_NAME.get(ticker, ticker)
            print(f"  [{ticker}] {company} 뉴스 수집 중...")

            articles = news_client.fetch_news(company, count=news_per_ticker)
            if not articles:
                continue

            for article in articles:
                result = sentiment.analyze(article["title"], company)
                if result is None:
                    continue

                conn.execute(
                    """INSERT INTO news_sentiment (ticker, date, title, url, score, summary)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (
                        ticker, today,
                        article["title"], article["url"],
                        result.get("score", 0.0),
                        result.get("summary", ""),
                    )
                )
                print(f"    [{result.get('score', 0):+.1f}] {article['title'][:40]}...")
                time.sleep(0.2)  # Claude API 호출 간격

            print(f"    → {len(articles)}개 기사 감성 분석 완료")
            time.sleep(0.5)

    print("\n[뉴스] 전체 수집 완료")


if __name__ == "__main__":
    init_db()
    collect_all(news_per_ticker=5)
