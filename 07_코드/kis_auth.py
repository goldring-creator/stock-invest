import json
import requests
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from config_loader import get_kis_config

TOKEN_CACHE = Path(__file__).parent / ".kis_token_cache.json"

def _load_cached_token() -> Optional[dict]:
    if not TOKEN_CACHE.exists():
        return None
    data = json.loads(TOKEN_CACHE.read_text())
    expires_at = datetime.fromisoformat(data["expires_at"])
    # 만료 5분 전이면 캐시 무효화
    if datetime.now() >= expires_at - timedelta(minutes=5):
        return None
    return data

def _save_token(token: str, expires_in: int):
    expires_at = datetime.now() + timedelta(seconds=expires_in)
    TOKEN_CACHE.write_text(json.dumps({
        "access_token": token,
        "expires_at": expires_at.isoformat()
    }))

def get_access_token() -> str:
    cached = _load_cached_token()
    if cached:
        return cached["access_token"]

    kis = get_kis_config()
    url = f"{kis['base_url']}/oauth2/tokenP"
    body = {
        "grant_type": "client_credentials",
        "appkey": kis["app_key"],
        "appsecret": kis["app_secret"]
    }
    resp = requests.post(url, json=body, timeout=10)
    resp.raise_for_status()
    data = resp.json()

    token = data["access_token"]
    expires_in = int(data.get("expires_in", 86400))
    _save_token(token, expires_in)
    print(f"[kis_auth] 새 토큰 발급 완료 (만료: {expires_in//3600}시간 후)")
    return token
