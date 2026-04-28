"""
매도 에이전트 — 익절/손절/시간만기 자동 매도
- 국내: 매일 15:00 KST 실행
- 해외: 매일 04:30 KST 실행 (US 장 마감 30분 전)
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from kis_trader import KisTrader
from notifier import notify_sell, notify_error
from database import get_conn
from datetime import date, datetime, timedelta

TAKE_PROFIT_PCT = 15.0   # +15% 익절
STOP_LOSS_PCT   = 8.0    # -8% 손절
MAX_HOLD_DAYS   = 22     # 22 거래일 (약 1개월)


def _trading_days_held(trader: KisTrader, ticker: str, market: str = "KR") -> int:
    """KIS VTS API로 최초 매수 체결일 조회 → 보유 거래일 계산.
    API 실패 시 로컬 DB로 fallback (원격 세션에선 항상 0 반환)."""
    try:
        start = (date.today() - timedelta(days=90)).strftime("%Y%m%d")
        today_str = date.today().strftime("%Y%m%d")
        acno = trader.cfg["account_no"].split("-")

        if market == "KR":
            data = trader.client.get(
                path="/uapi/domestic-stock/v1/trading/inquire-daily-ccld",
                tr_id=trader._ord_tr,
                params={
                    "CANO": acno[0], "ACNT_PRDT_CD": acno[1],
                    "INQR_STRT_DT": start, "INQR_END_DT": today_str,
                    "SLL_BUY_DVSN_CD": "02",
                    "INQR_DVSN": "00", "PDNO": ticker,
                    "CCLD_DVSN": "01",
                    "ORD_GNO_BRNO": "", "ODNO": "",
                    "INQR_DVSN_3": "00", "INQR_DVSN_1": "",
                    "CTX_AREA_FK100": "", "CTX_AREA_NK100": "",
                }
            )
            items = data.get("output1", [])
        else:
            tr_id = "VTTS3035R" if trader._is_mock else "TTTS3035R"
            data = trader.client.get(
                path="/uapi/overseas-stock/v1/trading/inquire-ccnl",
                tr_id=tr_id,
                params={
                    "CANO": acno[0], "ACNT_PRDT_CD": acno[1],
                    "PDNO": ticker, "SLL_BUY_DVSN_CD": "02",
                    "ORD_STRT_DT": start, "ORD_END_DT": today_str,
                    "CCLD_NCCS_DVSN": "01", "OVRS_EXCG_CD": "",
                    "SORT_SQN": "DS",
                    "CTX_AREA_FK200": "", "CTX_AREA_NK200": "",
                }
            )
            items = data.get("output", [])

        dates = [it.get("ord_dt", "") for it in items if it.get("ord_dt", "").strip()]
        if not dates:
            return 0
        first_date = datetime.strptime(min(dates), "%Y%m%d").date()
        return (date.today() - first_date).days

    except Exception as e:
        print(f"[sell_agent] {ticker} 보유기간 API 조회 실패: {e}")
        # 로컬 DB fallback
        try:
            with get_conn() as conn:
                row = conn.execute(
                    "SELECT MIN(date) as first_buy FROM trade_log "
                    "WHERE ticker=? AND order_type='BUY' AND market=?",
                    (ticker, market)
                ).fetchone()
            if row and row["first_buy"]:
                first_date = datetime.strptime(row["first_buy"], "%Y-%m-%d").date()
                return (date.today() - first_date).days
        except Exception:
            pass
        return 0


def check_domestic(trader: KisTrader) -> list:
    """국내 보유 종목 매도 신호 확인"""
    sell_targets = []
    try:
        bal = trader.get_balance()
        for h in bal.get("holdings", []):
            pnl_rate = h["pnl_rate"]
            hold_days = _trading_days_held(trader, h["ticker"], "KR")
            reason = None
            if pnl_rate >= TAKE_PROFIT_PCT:
                reason = "익절"
            elif pnl_rate <= -STOP_LOSS_PCT:
                reason = "손절"
            elif hold_days >= MAX_HOLD_DAYS:
                reason = f"만기청산({hold_days}일)"
            if reason:
                sell_targets.append({
                    "ticker": h["ticker"],
                    "name": h["name"],
                    "quantity": h["quantity"],
                    "price": h["current_price"],
                    "pnl_rate": pnl_rate,
                    "reason": reason,
                    "market": "KR",
                })
    except Exception as e:
        notify_error("SellAgent.check_domestic", str(e))
    return sell_targets


def check_overseas(trader: KisTrader) -> list:
    """해외 보유 종목 매도 신호 확인"""
    sell_targets = []
    try:
        holdings = trader.get_all_overseas_holdings()
        for h in holdings:
            pnl_rate = h["pnl_rate"]
            hold_days = _trading_days_held(trader, h["ticker"], "US")
            reason = None
            if pnl_rate >= TAKE_PROFIT_PCT:
                reason = "익절"
            elif pnl_rate <= -STOP_LOSS_PCT:
                reason = "손절"
            elif hold_days >= MAX_HOLD_DAYS:
                reason = f"만기청산({hold_days}일)"
            if reason:
                # 현재가 재확인
                try:
                    price_info = trader.get_overseas_price(h["ticker"], h["exchange"])
                    current_price = price_info["price_usd"]
                except Exception:
                    current_price = h["current_price_usd"]
                sell_targets.append({
                    "ticker": h["ticker"],
                    "name": h["name"],
                    "quantity": h["quantity"],
                    "price_usd": current_price,
                    "pnl_rate": pnl_rate,
                    "reason": reason,
                    "exchange": h["exchange"],
                    "market": "US",
                })
    except Exception as e:
        notify_error("SellAgent.check_overseas", str(e))
    return sell_targets


def run(market: str = "ALL") -> dict:
    """
    매도 에이전트 실행
    market: 'KR' | 'US' | 'ALL'
    """
    trader = KisTrader(dry_run=False)
    domestic_sells, overseas_sells, executed = [], [], []

    if market in ("KR", "ALL"):
        domestic_sells = check_domestic(trader)
        for s in domestic_sells:
            order_id = trader.sell_market(s["ticker"], s["quantity"])
            if order_id:
                executed.append(s)
                notify_sell(
                    "SELL", s["ticker"], s["name"],
                    s["quantity"], s["price"],
                    s["reason"], s["pnl_rate"], "KR"
                )
                print(f"[sell_agent] {s['reason']} 국내 매도: "
                      f"{s['name']} {s['quantity']}주 ({s['pnl_rate']:+.1f}%)")

    if market in ("US", "ALL"):
        overseas_sells = check_overseas(trader)
        for s in overseas_sells:
            order_id = trader.sell_limit_overseas(
                s["ticker"], s["quantity"], s["price_usd"], s["exchange"]
            )
            if order_id:
                executed.append(s)
                notify_sell(
                    "SELL", s["ticker"], s["name"],
                    s["quantity"], s["price_usd"],
                    s["reason"], s["pnl_rate"], "US"
                )
                print(f"[sell_agent] {s['reason']} 해외 매도: "
                      f"{s['name']} {s['quantity']}주 ({s['pnl_rate']:+.1f}%)")

    total_candidates = len(domestic_sells) + len(overseas_sells)
    print(f"[sell_agent] 완료: 매도 대상 {total_candidates}건 / 실행 {len(executed)}건")

    if not executed:
        print("[sell_agent] 매도 조건 충족 종목 없음")

    return {
        "executed": executed,
        "domestic_candidates": domestic_sells,
        "overseas_candidates": overseas_sells,
    }


if __name__ == "__main__":
    run("ALL")
