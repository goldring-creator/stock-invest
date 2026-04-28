"""
버핏 가디언 에이전트
버핏 주주서한에서 추출한 투자 원칙을 기반으로 종목을 APPROVE / REJECT / FLAG 판단.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import json
import anthropic
from dataclasses import dataclass
from datetime import date
from typing import List, Optional

from config_loader import get_claude_config
from database import get_conn
from notifier import notify_guardian

DIGEST_PATH = Path(__file__).parent.parent.parent / "01_버핏자료" / "버핏원칙_다이제스트.txt"

SYSTEM_TEMPLATE = """당신은 워런 버핏의 투자 철학을 완벽히 내면화한 투자 심사 에이전트입니다.
아래는 1977~2024년 버핏 주주서한에서 추출한 핵심 투자 원칙과 실제 발언입니다.
이를 근거로 주어진 종목을 엄격하게 심사하세요.

=== 버핏 투자 원칙 서한 발췌 ===
{digest}
=== 발췌 끝 ===

## 심사 기준 (버핏 6원칙)
1. **경제적 해자(Moat)**: 브랜드, 특허, 네트워크 효과, 전환 비용 등 지속 가능한 경쟁우위
2. **이해 가능한 사업**: 10년 후도 예측 가능한 단순한 비즈니스 모델
3. **장기 재무 건전성**: ROE 15% 이상 지속, 부채비율 낮음, 잉여현금흐름 안정
4. **정직하고 유능한 경영진**: 주주친화적 자본 배분, 투명한 공시
5. **합리적 주가(안전마진)**: 내재가치 대비 충분한 할인
6. **장기 보유 의향**: 최소 5년 이상 보유할 의향이 생기는가

## 출력 형식 (JSON만 반환, 다른 텍스트 없음)
{{
  "decision": "APPROVE" | "REJECT" | "FLAG",
  "score": 0~100,
  "principles": {{
    "moat": 0~20,
    "understandable": 0~20,
    "financials": 0~20,
    "management": 0~20,
    "valuation": 0~20
  }},
  "reason": "판단 이유 (3~5문장, 한국어)",
  "citations": ["버핏 서한 인용 1", "버핏 서한 인용 2"],
  "red_flags": ["위험 신호 1", "위험 신호 2"],
  "buffett_quote": "관련 버핏 명언 또는 서한 원문 발췌 (영문)"
}}

decision 기준:
- APPROVE (85점 이상): 버핏 원칙 전반에 부합, 매수 고려 가능
- FLAG (60~84점): 일부 원칙 부합하나 추가 검토 필요
- REJECT (60점 미만): 버핏 원칙에 명확히 위배, 매수 반대"""


@dataclass
class GuardianResult:
    ticker: str
    decision: str
    score: int
    principles: dict
    reason: str
    citations: List[str]
    red_flags: List[str]
    buffett_quote: str


class BuffettGuardian:
    def __init__(self):
        cfg = get_claude_config()
        self.client = anthropic.Anthropic(api_key=cfg["api_key"])
        self._system_prompt: Optional[str] = None

    def _get_system_prompt(self) -> str:
        if self._system_prompt is None:
            if DIGEST_PATH.exists():
                digest = DIGEST_PATH.read_text(encoding="utf-8")
                # 토큰 한도 고려: 최대 20,000자
                digest = digest[:20000]
            else:
                digest = "(버핏 서한 다이제스트 파일 없음 — 내장 원칙으로 판단)"
            self._system_prompt = SYSTEM_TEMPLATE.format(digest=digest)
        return self._system_prompt

    def analyze(self, ticker: str, company_info: dict) -> GuardianResult:
        """
        company_info 예시:
        {
            "name": "삼성전자",
            "sector": "반도체",
            "per": 12.5,
            "pbr": 1.2,
            "roe": 18.3,
            "debt_ratio": 35.0,
            "revenue_growth": 8.2,
            "operating_margin": 15.1,
            "description": "메모리 반도체 세계 1위, HBM 시장 선두"
        }
        """
        user_text = f"""다음 종목을 버핏 투자 원칙으로 심사해주세요.

## 종목 정보
- 티커: {ticker}
- 종목명: {company_info.get('name', '-')}
- 섹터: {company_info.get('sector', '-')}
- PER: {company_info.get('per', '-')}배
- PBR: {company_info.get('pbr', '-')}배
- ROE: {company_info.get('roe', '-')}%
- 부채비율: {company_info.get('debt_ratio', '-')}%
- 매출 성장률: {company_info.get('revenue_growth', '-')}%
- 영업이익률: {company_info.get('operating_margin', '-')}%
- 사업 설명: {company_info.get('description', '-')}

위 정보와 버핏 서한 원칙을 근거로 심사 결과를 JSON으로만 반환하세요."""

        print(f"  [guardian] {ticker} ({company_info.get('name', '')}) 분석 중...")

        resp = self.client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2048,
            system=self._get_system_prompt(),
            messages=[{"role": "user", "content": user_text}],
        )

        raw = resp.content[0].text.strip()
        # JSON 블록 추출
        if "```" in raw:
            parts = raw.split("```")
            raw = parts[1].replace("json", "").strip() if len(parts) > 1 else raw
        # JSON 시작 중괄호부터 끝까지만 추출
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start != -1 and end > start:
            raw = raw[start:end]

        data = json.loads(raw)

        result = GuardianResult(
            ticker=ticker,
            decision=data["decision"],
            score=int(data["score"]),
            principles=data.get("principles", {}),
            reason=data["reason"],
            citations=data.get("citations", []),
            red_flags=data.get("red_flags", []),
            buffett_quote=data.get("buffett_quote", ""),
        )

        self._save_to_db(result)
        self._print_result(result)
        # REJECT는 즉시 텔레그램 알림
        if result.decision in ("REJECT", "FLAG"):
            notify_guardian(
                result.ticker,
                company_info.get("name", result.ticker),
                result.decision,
                result.score,
                result.reason,
            )
        return result

    def _save_to_db(self, result: GuardianResult):
        with get_conn() as conn:
            conn.execute(
                """INSERT INTO buffett_decisions
                   (ticker, date, decision, score, reason, citations)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    result.ticker,
                    date.today().isoformat(),
                    result.decision,
                    result.score,
                    result.reason,
                    json.dumps(result.citations, ensure_ascii=False),
                )
            )

    def _print_result(self, result: GuardianResult):
        icons = {"APPROVE": "✅", "FLAG": "⚠️", "REJECT": "❌"}
        icon = icons.get(result.decision, "?")
        p = result.principles
        print(f"\n{'='*58}")
        print(f"  {icon} [{result.decision}]  {result.ticker}   총점: {result.score}/100")
        print(f"{'='*58}")
        print(f"  원칙별: 해자={p.get('moat',0)} 이해={p.get('understandable',0)} "
              f"재무={p.get('financials',0)} 경영={p.get('management',0)} "
              f"밸류={p.get('valuation',0)}")
        print(f"\n  판단: {result.reason}")
        if result.red_flags:
            print(f"\n  위험 신호:")
            for rf in result.red_flags:
                print(f"    • {rf}")
        if result.citations:
            print(f"\n  서한 근거:")
            for c in result.citations[:2]:
                print(f"    » {c[:85]}")
        if result.buffett_quote:
            print(f'\n  버핏 명언: "{result.buffett_quote[:100]}"')
        print(f"{'='*58}\n")
