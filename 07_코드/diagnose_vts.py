"""
VTS 계좌번호 진단 스크립트
INVALID_CHECK_ACNO 오류 원인 파악 및 올바른 계좌번호 탐색
"""
import sys
import json
import requests
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from kis_auth import get_access_token
from config_loader import get_kis_config

BASE_URL = "https://openapivts.koreainvestment.com:29443"

def get_headers(tr_id: str, cfg: dict, token: str) -> dict:
    return {
        "authorization": f"Bearer {token}",
        "appkey": cfg["app_key"],
        "appsecret": cfg["app_secret"],
        "tr_id": tr_id,
        "Content-Type": "application/json; charset=utf-8",
    }

def test_balance(cano: str, acnt_prdt_cd: str, cfg: dict, token: str) -> dict:
    params = {
        "CANO": cano,
        "ACNT_PRDT_CD": acnt_prdt_cd,
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
    resp = requests.get(
        f"{BASE_URL}/uapi/domestic-stock/v1/trading/inquire-balance",
        headers=get_headers("VTTC8434R", cfg, token),
        params=params,
        timeout=10,
    )
    return resp.json()

def test_buyable(cano: str, acnt_prdt_cd: str, cfg: dict, token: str) -> dict:
    params = {
        "CANO": cano,
        "ACNT_PRDT_CD": acnt_prdt_cd,
        "PDNO": "005930",
        "ORD_UNPR": "50000",
        "ORD_DVSN": "01",
        "CMA_EVLU_AMT_ICLD_YN": "N",
        "OVRS_ICLD_YN": "N",
    }
    resp = requests.get(
        f"{BASE_URL}/uapi/domestic-stock/v1/trading/inquire-psbl-order",
        headers=get_headers("VTTC8908R", cfg, token),
        params=params,
        timeout=10,
    )
    return resp.json()

def main():
    print("\n" + "="*60)
    print("  KIS VTS 계좌 진단 도구")
    print("="*60)

    cfg = get_kis_config()
    print(f"\n[설정 확인]")
    print(f"  APP_KEY   : {cfg['app_key'][:12]}...")
    print(f"  account_no: {cfg['account_no']}")
    print(f"  use_mock  : {cfg['use_mock']}")
    print(f"  base_url  : {cfg['base_url']}")

    print(f"\n[토큰 발급]")
    token = get_access_token()
    print(f"  토큰: {token[:20]}... (발급 완료)")

    raw_acno = cfg["account_no"]
    parts = raw_acno.split("-")
    cano_orig = parts[0]
    prdt_orig = parts[1] if len(parts) > 1 else "01"

    # 시도할 계좌번호 조합 목록
    candidates = []

    # 원본 계좌번호
    candidates.append((cano_orig, prdt_orig, "원본 config 값"))

    # 계좌번호 변형: 앞 8자리만 (혹시 뒤에 숫자가 붙어있다면)
    if len(cano_orig) > 8:
        candidates.append((cano_orig[:8], prdt_orig, "앞 8자리"))

    # 상품코드 01 / 21 / 51 변형
    for prdt in ["01", "21", "51"]:
        if prdt != prdt_orig:
            candidates.append((cano_orig, prdt, f"상품코드 {prdt}"))

    print(f"\n[잔고조회 API 테스트 — VTTC8434R]")
    print("-"*60)

    found = False
    for cano, prdt, label in candidates:
        print(f"\n  시도: CANO={cano}  ACNT_PRDT_CD={prdt}  ({label})")
        try:
            result = test_balance(cano, prdt, cfg, token)
            rt_cd = result.get("rt_cd", "?")
            msg = result.get("msg1", "")
            msg_cd = result.get("msg_cd", "")

            if rt_cd == "0":
                print(f"  ✅ 성공!")
                cash = result.get("output2", [{}])[0].get("dnca_tot_amt", "?")
                print(f"  예수금: {cash}원")
                print(f"\n  ✅ 올바른 계좌번호 확인!")
                print(f"  → config.yaml의 account_no를 {cano}-{prdt} 로 수정하세요")
                found = True
                break
            else:
                print(f"  ❌ 실패  rt_cd={rt_cd}  msg_cd={msg_cd}")
                print(f"     메시지: {msg}")
        except Exception as e:
            print(f"  ❌ 예외: {e}")

    if not found:
        print("\n" + "="*60)
        print("  모든 시도 실패 — 다음 중 하나를 확인하세요:")
        print()
        print("  1. KIS 개발자 포털에서 VTS 계좌번호 직접 확인")
        print("     → apiportal.koreainvestment.com → 로그인")
        print("     → 상단 메뉴 [앱 목록] → 등록한 앱 클릭")
        print("     → '모의투자계좌번호' 항목 확인 후 아래 공유")
        print()
        print("  2. TESTBED에서 직접 테스트")
        print("     → apiportal.koreainvestment.com → TESTBED")
        print("     → [국내주식] 주문/계좌 → 주식잔고조회")
        print(f"     → appkey: {cfg['app_key'][:12]}...")
        print(f"     → CANO 칸: 비워두고 SEND → 오류 메시지 확인")
        print()
        print("  3. 위 포털 화면 캡처해서 공유해주시면 같이 분석합니다")
        print("="*60)
    else:
        print("\n[매수가능조회 추가 테스트]")
        cano, prdt, _ = next(
            (c for c in candidates if c[2] != "실패"), candidates[0]
        )
        try:
            r = test_buyable(cano, prdt, cfg, token)
            if r.get("rt_cd") == "0":
                amt = r.get("output", {}).get("ord_psbl_cash", "?")
                print(f"  ✅ 주문가능금액: {amt}원")
            else:
                print(f"  ⚠️  매수가능조회: {r.get('msg1', '')}")
        except Exception as e:
            print(f"  ⚠️  매수가능조회 예외: {e}")

    print()

if __name__ == "__main__":
    main()
