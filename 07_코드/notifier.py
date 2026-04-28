"""
텔레그램 알림 모듈
시스템 전체에서 import해서 사용: from notifier import notify, notify_trade, notify_guardian
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import requests
from config_loader import get_telegram_config

TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"


def _send(text: str, parse_mode: str = "HTML") -> bool:
    try:
        cfg = get_telegram_config()
        token = cfg.get("bot_token", "")
        chat_id = cfg.get("chat_id", "")
        if not token or not chat_id:
            return False
        payload: dict = {"chat_id": chat_id, "text": text}
        if parse_mode:
            payload["parse_mode"] = parse_mode
        resp = requests.post(
            TELEGRAM_API.format(token=token),
            json=payload,
            timeout=10,
        )
        result = resp.json()
        if not result.get("ok", False):
            print(f"[notifier] Telegram 거부: {result.get('description', result)}")
        return result.get("ok", False)
    except Exception as e:
        print(f"[notifier] 전송 실패: {e}")
        return False


def notify(message: str) -> bool:
    """일반 텍스트 알림"""
    return _send(message)


def notify_guardian(ticker: str, name: str, decision: str, score: int, reason: str) -> bool:
    """버핏 가디언 판단 결과 알림"""
    icons = {"APPROVE": "✅", "FLAG": "⚠️", "REJECT": "❌"}
    icon = icons.get(decision, "?")
    text = (
        f"{icon} <b>버핏 가디언 판단</b>\n"
        f"종목: {name} ({ticker})\n"
        f"결론: <b>{decision}</b>  점수: {score}/100\n"
        f"─────────────────\n"
        f"{reason[:300]}"
    )
    return _send(text)


def notify_trade(order_type: str, ticker: str, name: str,
                 quantity: int, price: int, status: str) -> bool:
    """매매 주문 알림"""
    icons = {"BUY": "📈", "SELL": "📉"}
    icon = icons.get(order_type, "📊")
    amount = quantity * price
    text = (
        f"{icon} <b>주문 {status}</b>\n"
        f"종류: {order_type}  {name} ({ticker})\n"
        f"수량: {quantity:,}주  단가: {price:,}원\n"
        f"금액: {amount:,}원"
    )
    return _send(text)


def notify_sell(order_type: str, ticker: str, name: str,
                quantity: int, price: float, reason: str,
                pnl_rate: float, market: str = "KR") -> bool:
    """매도 실행 알림 (익절/손절)"""
    icon = "💰" if "익절" in reason else "🛑"
    currency = "원" if market == "KR" else "USD"
    price_str = f"{int(price):,}{currency}" if market == "KR" else f"${price:.2f}"
    sign = "+" if pnl_rate >= 0 else ""
    text = (
        f"{icon} <b>매도 실행 ({reason})</b>\n"
        f"종목: {name} ({ticker})\n"
        f"수량: {quantity:,}주  단가: {price_str}\n"
        f"수익률: {sign}{pnl_rate:.1f}%"
    )
    return _send(text)


def notify_error(source: str, error: str) -> bool:
    """오류 알림 — HTML 없이 plain text 전송 (에러 메시지 내 특수문자 안전)"""
    text = (
        f"🚨 오류 발생\n"
        f"위치: {source}\n"
        f"내용: {error[:300]}"
    )
    return _send(text, parse_mode="")


def notify_daily_summary(date: str, portfolio_value: int,
                         daily_pnl: int, daily_pnl_rate: float) -> bool:
    """일별 포트폴리오 요약 알림"""
    sign = "+" if daily_pnl >= 0 else ""
    text = (
        f"📊 <b>일별 성과 요약</b>  {date}\n"
        f"─────────────────\n"
        f"평가금액: {portfolio_value:,}원\n"
        f"당일 손익: {sign}{daily_pnl:,}원 ({sign}{daily_pnl_rate:.2f}%)"
    )
    return _send(text)


if __name__ == "__main__":
    # 테스트
    ok = notify("🔔 notifier 모듈 테스트 메시지입니다.")
    print("전송 성공" if ok else "전송 실패")

    ok = notify_guardian("005930", "삼성전자", "FLAG", 67,
                         "ROE 8.2%로 기준 미달이나 저평가 매력 존재. 추가 검토 권장.")
    print("가디언 알림:", "성공" if ok else "실패")
