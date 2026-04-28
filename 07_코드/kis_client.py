import requests
from kis_auth import get_access_token
from kis_throttle import throttle
from config_loader import get_kis_config

# TLS 1.2 이상 강제 (2025-12-12 이후 KIS 필수)
requests.packages.urllib3.util.ssl_.DEFAULT_CIPHERS = "HIGH:!DH:!aNULL"

class KisClient:
    def __init__(self):
        self.cfg = get_kis_config()
        self.base_url = self.cfg["base_url"]

    def _headers(self, tr_id: str) -> dict:
        return {
            "authorization": f"Bearer {get_access_token()}",
            "appkey": self.cfg["app_key"],
            "appsecret": self.cfg["app_secret"],
            "tr_id": tr_id,
            "Content-Type": "application/json; charset=utf-8",
        }

    def get(self, path: str, tr_id: str, params: dict) -> dict:
        throttle.wait()
        url = f"{self.base_url}{path}"
        resp = requests.get(url, headers=self._headers(tr_id), params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if data.get("rt_cd") != "0":
            raise RuntimeError(f"KIS API 오류: {data.get('msg1', data)}")
        return data

    def post(self, path: str, tr_id: str, body: dict) -> dict:
        throttle.wait()
        url = f"{self.base_url}{path}"
        resp = requests.post(url, headers=self._headers(tr_id), json=body, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if data.get("rt_cd") != "0":
            raise RuntimeError(f"KIS API 오류: {data.get('msg1', data)}")
        return data

    def get_stock_price(self, ticker: str) -> dict:
        """국내 주식 현재가 조회"""
        # 모의투자는 FHKST01010100, 실전도 동일
        data = self.get(
            path="/uapi/domestic-stock/v1/quotations/inquire-price",
            tr_id="FHKST01010100",
            params={"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": ticker}
        )
        output = data["output"]
        return {
            "ticker": ticker,
            "name": output.get("hts_kor_isnm", ""),
            "price": int(output.get("stck_prpr", 0)),
            "change_rate": float(output.get("prdy_ctrt", 0)),
            "volume": int(output.get("acml_vol", 0)),
        }
