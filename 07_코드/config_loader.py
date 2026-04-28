import yaml
from pathlib import Path

CONFIG_PATH = Path(__file__).parent.parent / "06_설정파일" / "config.yaml"

def load_config() -> dict:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)

def get_kis_config() -> dict:
    cfg = load_config()
    use_mock = cfg["kis"]["use_mock"]
    env = "mock" if use_mock else "real"
    kis = cfg["kis"][env]
    kis["use_mock"] = use_mock
    kis["base_url"] = (
        "https://openapivts.koreainvestment.com:29443" if use_mock
        else "https://openapi.koreainvestment.com:9443"
    )
    return kis

def get_naver_config() -> dict:
    return load_config()["naver"]

def get_dart_config() -> dict:
    return load_config()["dart"]

def get_claude_config() -> dict:
    return load_config()["claude"]

def get_telegram_config() -> dict:
    return load_config()["telegram"]
