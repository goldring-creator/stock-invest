"""
KIS API 연결 테스트
실행: python test_connection.py
성공 시: 삼성전자 현재가 출력
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from kis_client import KisClient
from config_loader import get_kis_config

def main():
    cfg = get_kis_config()
    env = "모의투자" if cfg["use_mock"] else "실전"
    print(f"\n{'='*40}")
    print(f"  KIS API 연결 테스트 [{env}]")
    print(f"  계좌번호: {cfg['account_no']}")
    print(f"{'='*40}\n")

    client = KisClient()

    # 삼성전자 현재가 조회
    print("▶ 삼성전자(005930) 현재가 조회 중...")
    result = client.get_stock_price("005930")

    print(f"\n✅ 연결 성공!")
    print(f"   종목명: {result['name']}")
    print(f"   현재가: {result['price']:,}원")
    print(f"   등락률: {result['change_rate']:+.2f}%")
    print(f"   거래량: {result['volume']:,}주")
    print(f"\n{'='*40}")
    print("  Phase 1 기반 환경 구축 완료")
    print(f"{'='*40}\n")

if __name__ == "__main__":
    main()
