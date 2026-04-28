"""
KIS 모의투자 매매 모듈
- 매수/매도 주문 (지정가·시장가)
- 체결 확인 폴링
- 잔고 및 포트폴리오 조회
- 과주문 하드 제한 (일 10건, 건당 100만원)
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import time
from datetime import date
from typing import Optional

from kis_client import KisClient
from config_loader import get_kis_config
from database import get_conn
from notifier import notify_trade, notify_error

# 안전 제한 (모의투자 중에는 보수적으로 설정)
MAX_ORDERS_PER_DAY = 10
MAX_AMOUNT_PER_ORDER = 1_000_000   # 100만원


class KisTrader:
    def __init__(self, dry_run: bool = True):
        """
        dry_run=True  → 주문 로그·텔레그램 알림만 발송, KIS 실제 API 호출 없음
        dry_run=False → KIS VTS(모의투자) 또는 실전 API 실제 호출
        """
        self.dry_run = dry_run
        self.client = KisClient()
        self.cfg = get_kis_config()
        self._is_mock = self.cfg["use_mock"]
        # 모의투자 tr_id 매핑
        self._buy_tr  = "VTTC0802U" if self._is_mock else "TTTC0802U"
        self._sell_tr = "VTTC0801U" if self._is_mock else "TTTC0801U"
        self._bal_tr  = "VTTC8434R" if self._is_mock else "TTTC8434R"
        self._ord_tr  = "VTTC8001R" if self._is_mock else "TTTC8001R"
        # 해외주식 TR_ID
        self._buy_tr_os  = "VTTT1002U" if self._is_mock else "TTTT1002U"
        self._sell_tr_os = "VTTT1006U" if self._is_mock else "TTTT1006U"
        self._bal_tr_os  = "VTTS3012R" if self._is_mock else "TTTS3012R"
        # 거래소 코드 매핑 (주문용 → 현재가조회용)
        self._excg_price_map = {"NASD": "NAS", "NYSE": "NYS", "AMEX": "AMS"}
        if dry_run:
            print("[trader] ⚠️  드라이런 모드 — 실제 주문 없음, 로그·알림만 발송")

    # ── 안전 제한 확인 ──────────────────────────────────────────
    def _check_daily_limit(self) -> bool:
        today = date.today().isoformat()
        with get_conn() as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM trade_log WHERE date=? AND status!='CANCELLED'",
                (today,)
            ).fetchone()[0]
        if count >= MAX_ORDERS_PER_DAY:
            msg = f"일일 주문 한도 초과 ({count}/{MAX_ORDERS_PER_DAY}건)"
            print(f"[trader] ⛔ {msg}")
            notify_error("KisTrader", msg)
            return False
        return True

    def remaining_daily_orders(self) -> int:
        """오늘 남은 주문 가능 건수"""
        today = date.today().isoformat()
        with get_conn() as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM trade_log WHERE date=? AND status!='CANCELLED'",
                (today,)
            ).fetchone()[0]
        return max(0, MAX_ORDERS_PER_DAY - count)

    def _check_amount_limit(self, quantity: int, price: int) -> bool:
        amount = quantity * price
        if amount > MAX_AMOUNT_PER_ORDER:
            msg = f"건당 주문 한도 초과 ({amount:,}원 > {MAX_AMOUNT_PER_ORDER:,}원)"
            print(f"[trader] ⛔ {msg}")
            notify_error("KisTrader", msg)
            return False
        return True

    # ── 주문 공통 ───────────────────────────────────────────────
    def _place_order(self, order_type: str, ticker: str,
                     quantity: int, price: int, market: bool = False) -> Optional[str]:
        """
        order_type: 'BUY' | 'SELL'
        market: True=시장가, False=지정가
        반환: 주문번호 or None(실패)
        """
        if not self._check_daily_limit():
            return None
        if not market and not self._check_amount_limit(quantity, price):
            return None

        tr_id = self._buy_tr if order_type == "BUY" else self._sell_tr
        ord_dvsn = "01" if market else "00"   # 01=시장가, 00=지정가
        ord_price = "0" if market else str(price)

        body = {
            "CANO": self.cfg["account_no"].split("-")[0],
            "ACNT_PRDT_CD": self.cfg["account_no"].split("-")[1],
            "PDNO": ticker,
            "ORD_DVSN": ord_dvsn,
            "ORD_QTY": str(quantity),
            "ORD_UNPR": ord_price,
        }

        price_label = '시장가' if market else f'{price:,}원'

        if self.dry_run:
            import uuid
            order_id = f"DRY-{uuid.uuid4().hex[:8].upper()}"
            print(f"[trader] 🧪 드라이런 {order_type}: {ticker} {quantity}주 "
                  f"{price_label} → 가상주문번호 {order_id}")
            self._log_order(order_type, ticker, quantity, price, order_id)
            notify_trade(order_type, ticker, ticker, quantity, price, "드라이런접수")
            return order_id

        try:
            data = self.client.post(
                path="/uapi/domestic-stock/v1/trading/order-cash",
                tr_id=tr_id,
                body=body,
            )
            order_id = data.get("output", {}).get("ODNO", "")
            print(f"[trader] {order_type} 주문 접수: {ticker} {quantity}주 "
                  f"{price_label} → 주문번호 {order_id}")
            self._log_order(order_type, ticker, quantity, price, order_id)
            notify_trade(order_type, ticker, ticker, quantity, price, "주문접수")
            return order_id
        except Exception as e:
            msg = f"{order_type} 주문 실패 ({ticker}): {e}"
            print(f"[trader] ❌ {msg}")
            notify_error("KisTrader._place_order", msg)
            return None

    def _log_order(self, order_type: str, ticker: str,
                   quantity: int, price: int, order_id: str):
        with get_conn() as conn:
            conn.execute(
                """INSERT INTO trade_log
                   (ticker, date, order_type, quantity, price, amount, order_id, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 'PENDING')""",
                (ticker, date.today().isoformat(),
                 order_type, quantity, price, quantity * price, order_id)
            )

    # ── 공개 주문 메서드 ─────────────────────────────────────────
    def buy(self, ticker: str, quantity: int, price: int) -> Optional[str]:
        """지정가 매수"""
        return self._place_order("BUY", ticker, quantity, price, market=False)

    def sell(self, ticker: str, quantity: int, price: int) -> Optional[str]:
        """지정가 매도"""
        return self._place_order("SELL", ticker, quantity, price, market=False)

    def buy_market(self, ticker: str, quantity: int) -> Optional[str]:
        """시장가 매수"""
        return self._place_order("BUY", ticker, quantity, 0, market=True)

    def sell_market(self, ticker: str, quantity: int) -> Optional[str]:
        """시장가 매도"""
        return self._place_order("SELL", ticker, quantity, 0, market=True)

    # ── 체결 확인 폴링 ───────────────────────────────────────────
    def wait_for_fill(self, order_id: str, ticker: str,
                      timeout: int = 60, interval: int = 5) -> bool:
        """
        최대 timeout초 동안 체결 여부를 interval초마다 확인.
        체결 시 True, 시간 초과 시 False 반환.
        """
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                data = self.client.get(
                    path="/uapi/domestic-stock/v1/trading/inquire-daily-ccld",
                    tr_id=self._ord_tr,
                    params={
                        "CANO": self.cfg["account_no"].split("-")[0],
                        "ACNT_PRDT_CD": self.cfg["account_no"].split("-")[1],
                        "INQR_STRT_DT": date.today().strftime("%Y%m%d"),
                        "INQR_END_DT": date.today().strftime("%Y%m%d"),
                        "SLL_BUY_DVSN_CD": "00",
                        "INQR_DVSN": "00",
                        "PDNO": ticker,
                        "CCLD_DVSN": "01",  # 체결만
                        "ORD_GNO_BRNO": "",
                        "ODNO": order_id,
                        "INQR_DVSN_3": "00",
                        "INQR_DVSN_1": "",
                        "CTX_AREA_FK100": "",
                        "CTX_AREA_NK100": "",
                    }
                )
                items = data.get("output1", [])
                if items:
                    item = items[0]
                    filled_qty = int(item.get("tot_ccld_qty", 0))
                    filled_price = int(item.get("avg_prvs", 0))
                    if filled_qty > 0:
                        print(f"[trader] ✅ 체결 확인: {ticker} {filled_qty}주 @ {filled_price:,}원")
                        self._update_fill(order_id, filled_price)
                        return True
            except Exception as e:
                print(f"[trader] 체결 조회 오류: {e}")
            time.sleep(interval)

        print(f"[trader] ⏰ 체결 대기 시간 초과 ({timeout}초): {order_id}")
        return False

    def _update_fill(self, order_id: str, fill_price: int):
        with get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM trade_log WHERE order_id=?", (order_id,)
            ).fetchone()
            if row:
                conn.execute(
                    "UPDATE trade_log SET status='FILLED', price=? WHERE order_id=?",
                    (fill_price, order_id)
                )
                notify_trade(
                    row["order_type"], row["ticker"], row["ticker"],
                    row["quantity"], fill_price, "체결"
                )

    # ── 잔고 조회 ────────────────────────────────────────────────
    def get_balance(self) -> dict:
        """예수금 + 보유 종목 조회"""
        if self.dry_run:
            with get_conn() as conn:
                rows = conn.execute(
                    "SELECT * FROM trade_log WHERE status IN ('PENDING','FILLED')"
                ).fetchall()
            holdings = {}
            for r in rows:
                t = r["ticker"]
                if r["order_type"] == "BUY":
                    if t not in holdings:
                        holdings[t] = {"quantity": 0, "total_cost": 0}
                    holdings[t]["quantity"] += r["quantity"]
                    holdings[t]["total_cost"] += r["amount"]
                elif r["order_type"] == "SELL" and t in holdings:
                    holdings[t]["quantity"] -= r["quantity"]
            holding_list = []
            for ticker, h in holdings.items():
                if h["quantity"] > 0:
                    avg = h["total_cost"] // h["quantity"]
                    holding_list.append({
                        "ticker": ticker, "name": ticker,
                        "quantity": h["quantity"], "avg_price": avg,
                        "current_price": avg, "eval_amount": avg * h["quantity"],
                        "pnl": 0, "pnl_rate": 0.0,
                    })
            return {"cash": 100_000_000, "total_eval": 100_000_000,
                    "total_pnl": 0, "holdings": holding_list}

        acno = self.cfg["account_no"].split("-")
        data = self.client.get(
            path="/uapi/domestic-stock/v1/trading/inquire-balance",
            tr_id=self._bal_tr,
            params={
                "CANO": acno[0],
                "ACNT_PRDT_CD": acno[1],
                "AFHR_FLPR_YN": "N",
                "OFL_YN": "N",
                "INQR_DVSN": "02",
                "UNPR_DVSN": "01",
                "FUND_STTL_ICLD_YN": "N",
                "FNCG_AMT_AUTO_RDPT_YN": "N",
                "PRCS_DVSN": "01",
                "CTX_AREA_FK100": "",
                "CTX_AREA_NK100": "",
            }
        )

        summary = data.get("output2", [{}])[0]
        holdings = []
        for item in data.get("output1", []):
            qty = int(item.get("hldg_qty", 0))
            if qty == 0:
                continue
            holdings.append({
                "ticker": item.get("pdno", ""),
                "name": item.get("prdt_name", ""),
                "quantity": qty,
                "avg_price": int(float(item.get("pchs_avg_pric", 0))),
                "current_price": int(float(item.get("prpr", 0))),
                "eval_amount": int(float(item.get("evlu_amt", 0))),
                "pnl": int(float(item.get("evlu_pfls_amt", 0))),
                "pnl_rate": float(item.get("evlu_pfls_rt", 0)),
            })

        return {
            "cash": int(float(summary.get("dnca_tot_amt", 0))),
            "total_eval": int(float(summary.get("tot_evlu_amt", 0))),
            "total_pnl": int(float(summary.get("evlu_pfls_smtl_amt", 0))),
            "holdings": holdings,
        }

    # ── 해외주식 현재가 조회 ─────────────────────────────────────
    def get_overseas_price(self, ticker: str, exchange: str) -> dict:
        """해외주식 현재가 조회 (USD)"""
        excd = self._excg_price_map.get(exchange, exchange[:3])
        data = self.client.get(
            path="/uapi/overseas-price/v1/quotations/price",
            tr_id="HHDFS76200A",
            params={"AUTH": "", "EXCD": excd, "SYMB": ticker}
        )
        output = data.get("output", {})
        return {
            "ticker": ticker,
            "exchange": exchange,
            "price_usd": float(output.get("last", 0) or 0),
            "change_pct": float(output.get("rate", 0) or 0),
            "name": output.get("name", ticker),
        }

    # ── 해외주식 주문 ────────────────────────────────────────────
    def _log_order_overseas(self, order_type: str, ticker: str,
                            quantity: int, price_usd: float,
                            exchange: str, order_id: str):
        with get_conn() as conn:
            conn.execute(
                """INSERT INTO trade_log
                   (ticker, date, order_type, quantity, price, amount, order_id, status,
                    market, exchange, currency, price_usd)
                   VALUES (?, ?, ?, ?, 0, 0, ?, 'PENDING', 'US', ?, 'USD', ?)""",
                (ticker, date.today().isoformat(),
                 order_type, quantity, order_id, exchange, price_usd)
            )

    def buy_limit_overseas(self, ticker: str, quantity: int,
                           price_usd: float, exchange: str = "NASD") -> Optional[str]:
        """해외주식 지정가 매수 (현재가 기준 +0.3% 여유 포함)"""
        if not self._check_daily_limit():
            return None

        order_price = round(price_usd * 1.003, 2)  # 슬리피지 여유

        if self.dry_run:
            import uuid
            order_id = f"DRY-OS-{uuid.uuid4().hex[:8].upper()}"
            print(f"[trader] 🧪 드라이런 BUY(US): {ticker} {quantity}주 "
                  f"${order_price:.2f} [{exchange}] → {order_id}")
            self._log_order_overseas("BUY", ticker, quantity, price_usd, exchange, order_id)
            return order_id

        body = {
            "CANO": self.cfg["account_no"].split("-")[0],
            "ACNT_PRDT_CD": self.cfg["account_no"].split("-")[1],
            "OVRS_EXCG_CD": exchange,
            "PDNO": ticker,
            "ORD_DVSN": "00",
            "ORD_QTY": str(quantity),
            "OVRS_ORD_UNPR": f"{order_price:.2f}",
            "ORD_SVR_DVSN_CD": "0",
        }
        try:
            data = self.client.post(
                path="/uapi/overseas-stock/v1/trading/order",
                tr_id=self._buy_tr_os,
                body=body,
            )
            order_id = data.get("output", {}).get("ODNO", "")
            print(f"[trader] BUY(US) 접수: {ticker} {quantity}주 ${order_price:.2f} "
                  f"[{exchange}] → {order_id}")
            self._log_order_overseas("BUY", ticker, quantity, price_usd, exchange, order_id)
            notify_trade("BUY", ticker, ticker, quantity, int(price_usd * 1400), "해외주문접수")
            return order_id
        except Exception as e:
            print(f"[trader] ❌ BUY(US) 실패 ({ticker}): {e}")
            notify_error("KisTrader.buy_limit_overseas", str(e))
            return None

    def sell_limit_overseas(self, ticker: str, quantity: int,
                            price_usd: float, exchange: str = "NASD") -> Optional[str]:
        """해외주식 지정가 매도 (현재가 기준 -0.3% 여유)"""
        if not self._check_daily_limit():
            return None

        order_price = round(price_usd * 0.997, 2)

        if self.dry_run:
            import uuid
            order_id = f"DRY-OS-{uuid.uuid4().hex[:8].upper()}"
            print(f"[trader] 🧪 드라이런 SELL(US): {ticker} {quantity}주 "
                  f"${order_price:.2f} [{exchange}] → {order_id}")
            self._log_order_overseas("SELL", ticker, quantity, price_usd, exchange, order_id)
            return order_id

        body = {
            "CANO": self.cfg["account_no"].split("-")[0],
            "ACNT_PRDT_CD": self.cfg["account_no"].split("-")[1],
            "OVRS_EXCG_CD": exchange,
            "PDNO": ticker,
            "ORD_DVSN": "00",
            "ORD_QTY": str(quantity),
            "OVRS_ORD_UNPR": f"{order_price:.2f}",
            "ORD_SVR_DVSN_CD": "0",
        }
        try:
            data = self.client.post(
                path="/uapi/overseas-stock/v1/trading/order",
                tr_id=self._sell_tr_os,
                body=body,
            )
            order_id = data.get("output", {}).get("ODNO", "")
            print(f"[trader] SELL(US) 접수: {ticker} {quantity}주 ${order_price:.2f} "
                  f"[{exchange}] → {order_id}")
            self._log_order_overseas("SELL", ticker, quantity, price_usd, exchange, order_id)
            notify_trade("SELL", ticker, ticker, quantity, int(price_usd * 1400), "해외매도접수")
            return order_id
        except Exception as e:
            print(f"[trader] ❌ SELL(US) 실패 ({ticker}): {e}")
            notify_error("KisTrader.sell_limit_overseas", str(e))
            return None

    # ── 해외주식 잔고 조회 ───────────────────────────────────────
    def get_overseas_balance(self, exchange: str = "NASD") -> list:
        """해외 보유 종목 조회"""
        acno = self.cfg["account_no"].split("-")
        try:
            data = self.client.get(
                path="/uapi/overseas-stock/v1/trading/inquire-balance",
                tr_id=self._bal_tr_os,
                params={
                    "CANO": acno[0],
                    "ACNT_PRDT_CD": acno[1],
                    "OVRS_EXCG_CD": exchange,
                    "TR_CRCY_CD": "USD",
                    "CTX_AREA_FK200": "",
                    "CTX_AREA_NK200": "",
                }
            )
        except RuntimeError:
            return []

        holdings = []
        for item in data.get("output1", []):
            qty = int(item.get("rmnd_qty", 0) or 0)
            if qty == 0:
                continue
            holdings.append({
                "ticker": item.get("ovrs_pdno", ""),
                "name": item.get("ovrs_item_name", ticker if (ticker := item.get("ovrs_pdno","")) else ""),
                "exchange": exchange,
                "quantity": qty,
                "avg_price_usd": float(item.get("pchs_avg_pric", 0) or 0),
                "current_price_usd": float(item.get("now_pric2", 0) or 0),
                "eval_amount_usd": float(item.get("ovrs_stck_evlu_amt", 0) or 0),
                "pnl_usd": float(item.get("frcr_evlu_pfls_amt", 0) or 0),
                "pnl_rate": float(item.get("evlu_pfls_rt", 0) or 0),
            })
        return holdings

    def get_all_overseas_holdings(self) -> list:
        """전체 해외 보유 종목 (NASD + NYSE + AMEX)"""
        all_holdings = []
        for excg in ["NASD", "NYSE", "AMEX"]:
            all_holdings.extend(self.get_overseas_balance(excg))
        return all_holdings

    def print_balance(self):
        bal = self.get_balance()
        env = "모의투자" if self._is_mock else "실전"
        print(f"\n{'='*50}")
        print(f"  포트폴리오 현황 [{env}]")
        print(f"{'='*50}")
        print(f"  예수금:    {bal['cash']:>15,}원")
        print(f"  평가금액:  {bal['total_eval']:>15,}원")
        print(f"  평가손익:  {bal['total_pnl']:>+15,}원")
        if bal["holdings"]:
            print(f"\n  보유 종목:")
            for h in bal["holdings"]:
                sign = "+" if h["pnl"] >= 0 else ""
                print(f"    {h['name']:12} {h['quantity']:>5}주  "
                      f"평균 {h['avg_price']:,}원  "
                      f"손익 {sign}{h['pnl_rate']:.1f}%")
        else:
            print("  보유 종목: 없음")
        print(f"{'='*50}\n")
