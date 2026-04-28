"""
버핏 주주서한 PDF → base64 변환 및 캐시 관리
Anthropic Prompt Caching으로 반복 분석 비용 90% 절감
"""
import base64
import hashlib
import json
from pathlib import Path
from typing import List

LETTERS_DIR = Path(__file__).parent.parent.parent / "01_버핏자료" / "주주서한"
CACHE_FILE = Path(__file__).parent / ".pdf_cache_meta.json"

PDF_FILES = [
    LETTERS_DIR / "버핏주주서한_전집_1977-2024.pdf",   # 8.7MB — 핵심 자료
    LETTERS_DIR / "버핏주주서한_2025.pdf",             # 92KB
    LETTERS_DIR / "버크셔해서웨이_2025_연간보고서.pdf", # 9.4MB
]


def _file_hash(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


def _load_cache() -> dict:
    if CACHE_FILE.exists():
        return json.loads(CACHE_FILE.read_text())
    return {}


def _save_cache(meta: dict):
    CACHE_FILE.write_text(json.dumps(meta, ensure_ascii=False, indent=2))


def get_pdf_blocks() -> List[dict]:
    """
    PDF들을 base64로 변환해 Anthropic document 블록 리스트로 반환.
    캐시를 활용해 파일이 변경되지 않으면 재변환을 건너뜀.
    반환 형식은 Claude API의 content 블록 형식.
    """
    cache = _load_cache()
    blocks = []
    updated = False

    for pdf_path in PDF_FILES:
        if not pdf_path.exists():
            print(f"  [pdf_loader] 파일 없음: {pdf_path.name}")
            continue

        file_hash = _file_hash(pdf_path)
        cached = cache.get(pdf_path.name, {})

        if cached.get("hash") == file_hash and "b64" in cached:
            b64_data = cached["b64"]
        else:
            print(f"  [pdf_loader] PDF 로드 중: {pdf_path.name} ({pdf_path.stat().st_size // 1024}KB)")
            raw = pdf_path.read_bytes()
            b64_data = base64.standard_b64encode(raw).decode("utf-8")
            cache[pdf_path.name] = {"hash": file_hash, "b64": b64_data}
            updated = True

        blocks.append({
            "type": "document",
            "source": {
                "type": "base64",
                "media_type": "application/pdf",
                "data": b64_data,
            },
            # cache_control은 Guardian에서 마지막 문서에 붙임
        })

    if updated:
        _save_cache(cache)

    # 마지막 document 블록에 cache_control 추가 (Anthropic Prompt Caching)
    if blocks:
        blocks[-1]["cache_control"] = {"type": "ephemeral"}

    print(f"  [pdf_loader] {len(blocks)}개 PDF 준비 완료")
    return blocks
