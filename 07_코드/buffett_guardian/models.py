from dataclasses import dataclass, field
from typing import List


@dataclass
class GuardianResult:
    ticker: str
    decision: str          # APPROVE / FLAG / REJECT
    score: int             # 0~100
    principles: dict       # moat/understandable/financials/management/valuation
    reason: str
    citations: List[str]   = field(default_factory=list)
    red_flags: List[str]   = field(default_factory=list)
    buffett_quote: str     = ""
