"""
DART OpenAPI 기반 분기별 재무제표 수집기
DART API 문서: https://opendart.fss.or.kr/guide/main.do
실행: python dart_collector.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import requests
import time
from typing import List, Optional

from config_loader import get_dart_config
from database import get_conn, init_db


# DART 재무제표 핵심 계정 코드 (단일 회사 재무제표 기준)
TARGET_ACCOUNTS = {
    "ifrs-full_Revenue": "매출액",
    "ifrs-full_GrossProfit": "매출총이익",
    "ifrs-full_OperatingIncome": "영업이익",
    "ifrs-full_ProfitLoss": "당기순이익",
    "ifrs-full_Assets": "총자산",
    "ifrs-full_Equity": "자기자본",
    "ifrs-full_Liabilities": "총부채",
    "dart_OperatingCashFlows": "영업활동현금흐름",
}

# 종목코드 → DART 기업고유번호 (주요 종목)
CORP_CODE_MAP = {
    "005930": "00126380",  # 삼성전자
    "000660": "00164779",  # SK하이닉스
    "005380": "00164742",  # 현대차
    "035420": "00266961",  # NAVER
    "051910": "00118016",  # LG화학
    "006400": "00126362",  # 삼성SDI
    "028260": "00126338",  # 삼성물산
    "012330": "00164718",  # 현대모비스
    "066570": "00401731",  # LG전자
    "003550": "00118011",  # LG
    "017670": "00131901",  # SK텔레콤
    "086790": "00547583",  # 하나금융지주
    "105560": "00247791",  # KB금융
    "055550": "00131901",  # 신한지주
    "000270": "00164780",  # 기아
}


class DartCollector:
    BASE_URL = "https://opendart.fss.or.kr/api"

    def __init__(self):
        self.api_key = get_dart_config()["api_key"]

    def _get(self, endpoint: str, params: dict) -> Optional[dict]:
        params["crtfc_key"] = self.api_key
        try:
            resp = requests.get(
                f"{self.BASE_URL}/{endpoint}",
                params=params,
                timeout=15
            )
            resp.raise_for_status()
            data = resp.json()
            if data.get("status") not in ("000", "013"):
                print(f"  [DART] API 오류: {data.get('message', data.get('status'))}")
                return None
            return data
        except Exception as e:
            print(f"  [DART] 요청 오류: {e}")
            return None

    def get_financial_statements(self, corp_code: str, year: int, quarter: int) -> List[dict]:
        """단일회사 주요재무제표 조회 (fnlttSinglAcntAll)"""
        reprt_code = {1: "11013", 2: "11012", 3: "11014", 4: "11011"}[quarter]

        data = self._get("fnlttSinglAcntAll.json", {
            "corp_code": corp_code,
            "bsns_year": str(year),
            "reprt_code": reprt_code,
            "fs_div": "CFS",  # 연결재무제표
        })

        if not data or "list" not in data:
            return []

        seen = set()
        results = []
        for item in data["list"]:
            account_id = item.get("account_id", "")
            if account_id not in TARGET_ACCOUNTS:
                continue
            # DART는 동일 account_id가 연결/별도/세부 항목으로 중복 반환됨
            # fs_nm이 '연결재무제표'인 첫 번째 행만 사용
            fs_nm = item.get("fs_nm", "")
            key = account_id
            if key in seen:
                continue
            if "연결" not in fs_nm and len(results) > 0:
                continue
            seen.add(key)
            try:
                value_str = item.get("thstrm_amount", "").replace(",", "").strip()
                value = float(value_str) if value_str else None
            except ValueError:
                value = None

            results.append({
                "account": TARGET_ACCOUNTS[account_id],
                "value": value,
                "unit": "원",
            })
        return results

    def collect_ticker(self, ticker: str, years: List[int], quarters: List[int] = None):
        if quarters is None:
            quarters = [1, 2, 3, 4]

        corp_code = CORP_CODE_MAP.get(ticker)
        if not corp_code:
            print(f"  [DART] {ticker}: corp_code 미등록, 건너뜀")
            return

        print(f"  [{ticker}] DART 재무 수집 중...")

        with get_conn() as conn:
            for year in years:
                for quarter in quarters:
                    period = f"{year}Q{quarter}"
                    items = self.get_financial_statements(corp_code, year, quarter)

                    if not items:
                        print(f"    {period}: 데이터 없음")
                        time.sleep(0.5)
                        continue

                    rows = [
                        {
                            "ticker": ticker,
                            "period": period,
                            "account": item["account"],
                            "value": item["value"],
                            "unit": item["unit"],
                        }
                        for item in items
                    ]
                    conn.executemany(
                        """INSERT OR REPLACE INTO financial_statement
                           (ticker, period, account, value, unit)
                           VALUES (:ticker, :period, :account, :value, :unit)""",
                        rows
                    )
                    print(f"    {period}: {len(rows)}개 계정 저장")
                    time.sleep(0.5)


def collect_all(tickers: List[str] = None, years: List[int] = None):
    if tickers is None:
        tickers = list(CORP_CODE_MAP.keys())
    if years is None:
        from datetime import date
        current_year = date.today().year
        years = [current_year - 1, current_year]

    collector = DartCollector()
    print(f"\n[DART] {len(tickers)}개 종목, {years} 연도 재무 수집 시작")

    for ticker in tickers:
        collector.collect_ticker(ticker, years)

    print("\n[DART] 전체 수집 완료")


if __name__ == "__main__":
    init_db()
    collect_all()
