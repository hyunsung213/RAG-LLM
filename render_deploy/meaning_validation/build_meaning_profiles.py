from __future__ import annotations

import csv
import json
import re
from collections import defaultdict
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
SEED_PATH = ROOT_DIR / "seed_cultural_words.csv"
ACCEPTED_PATH = ROOT_DIR / "output" / "validation" / "rag_documents_accepted.jsonl"
PROFILE_PATH = ROOT_DIR / "meaning_validation" / "meaning_profiles.json"

TOKEN_RE = re.compile(r"[가-힣A-Za-z0-9]+")
STOPWORDS = {
    "것", "수", "등", "때", "일", "그", "이", "저", "나", "너", "우리", "사람", "대상", "의미", "뜻",
    "단어", "품사", "발음", "명사", "형용사", "동사", "부사", "구", "또는", "하고", "하는", "있다", "이다",
}
PHYSICAL_MISMATCH_TERMS = [
    "색깔", "길이", "온도", "버튼", "배터리", "잔량", "숫자", "번호", "단위", "운동화", "끈", "방법",
    "라면", "물", "양", "화면", "밝기", "의자", "손잡이", "세탁기", "회전", "속도", "케이블",
    "냉장고", "문", "동작", "신발", "무게", "형광등", "전압", "책상", "다리", "지하철", "노선",
    "냄비", "뚜껑", "지름", "물병", "우산", "프린터", "잉크", "점도", "계산기", "와이파이",
    "비밀번호", "재질", "전등", "스위치", "전선", "노트북", "커피",
]
DOMAIN_INVALID_TERMS = {
    "권선징악": ["이익", "돈", "수익", "재물", "실속", "가격"],
    "신경 쓰다": ["생물", "신경계", "nerve", "전선"],
    "충": ["곤충", "벌레", "충전", "충격"],
    "정": ["정 그렇다면", "부사"],
    "한": ["하나", "한 개", "한 명", "한 번"],
}
DOMAIN_VALID_TERMS = {
    "권선징악": ["선", "악", "착한", "못된", "벌", "징계", "응징", "보상", "권장"],
    "신경 쓰다": ["마음", "관심", "살피", "걱정", "배려", "주의"],
}


def extract_terms(text: str, *, excluded: set[str] | None = None) -> list[str]:
    excluded = excluded or set()
    terms: list[str] = []
    for token in TOKEN_RE.findall(text or ""):
        if len(token) < 2 or token in STOPWORDS or token in excluded:
            continue
        if token not in terms:
            terms.append(token)
    return terms


def load_seed_rows() -> list[dict]:
    with SEED_PATH.open("r", encoding="utf-8-sig", newline="") as f:
        return [dict(row) for row in csv.DictReader(f)]


def load_definition_sources() -> dict[str, dict[str, list[str]]]:
    grouped: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    if not ACCEPTED_PATH.exists():
        return grouped

    with ACCEPTED_PATH.open("r", encoding="utf-8-sig") as f:
        for line in f:
            if not line.strip():
                continue
            doc = json.loads(line)
            word = str(doc.get("word", "")).strip()
            source = str((doc.get("metadata") or {}).get("source", doc.get("source", ""))).strip()
            content = str(doc.get("content", "")).strip()
            if word and source and content and content not in grouped[word][source]:
                grouped[word][source].append(content)
    return grouped


def build_profile(row: dict, definitions: dict[str, list[str]]) -> dict:
    word = str(row.get("word", "")).strip()
    excluded = {word}
    definition_text = " ".join(sum((items for items in definitions.values()), []))
    seed_text = " ".join(
        str(row.get(key, ""))
        for key in ["brief_meaning", "reason", "example", "culture_tags"]
    )
    excluded_text = str(row.get("excluded_meaning", ""))

    valid_terms = extract_terms(seed_text + " " + definition_text, excluded=excluded)
    invalid_terms = []
    invalid_terms.extend(DOMAIN_INVALID_TERMS.get(word, []))
    invalid_terms.extend(extract_terms(excluded_text, excluded=excluded))
    invalid_terms.extend(PHYSICAL_MISMATCH_TERMS)

    for term in DOMAIN_VALID_TERMS.get(word, []):
        if term not in valid_terms:
            valid_terms.append(term)

    return {
        "word": word,
        "pos": row.get("pos", ""),
        "brief_meaning": row.get("brief_meaning", ""),
        "excluded_meaning": row.get("excluded_meaning", ""),
        "reference_example": row.get("example", ""),
        "tags": [tag for tag in str(row.get("culture_tags", "")).split("|") if tag],
        "definition_sources": definitions,
        "valid_context_terms": valid_terms[:40],
        "invalid_context_terms": list(dict.fromkeys(invalid_terms))[:80],
    }


def build_profiles() -> dict:
    source_map = load_definition_sources()
    profiles = {}
    for row in load_seed_rows():
        word = str(row.get("word", "")).strip()
        if not word:
            continue
        profiles[word] = build_profile(row, dict(source_map.get(word, {})))
    return profiles


def main() -> None:
    profiles = build_profiles()
    PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    PROFILE_PATH.write_text(json.dumps(profiles, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"profiles": len(profiles), "path": str(PROFILE_PATH)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
