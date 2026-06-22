from __future__ import annotations

import json
import re
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
PROFILE_PATH = ROOT_DIR / "meaning_validation" / "meaning_profiles.json"
TOKEN_RE = re.compile(r"[가-힣A-Za-z0-9]+")

ABSTRACT_DEFINITION_HINTS = [
    "마음",
    "감정",
    "관계",
    "태도",
    "도리",
    "생각",
    "분위기",
    "정도",
    "능력",
    "일",
]
OBJECT_DEFINITION_PATTERNS = [
    r"은\s+.+이다",
    r"는\s+.+이다",
    r"이\s+.+이다",
    r"가\s+.+이다",
    r"뜻한다",
    r"의미한다",
]
GENERIC_VALID_TERMS = {
    "감정",
    "마음",
    "기분",
    "태도",
    "생각",
    "정도",
    "능력",
    "관계",
    "상황",
    "느낌",
}
PARTICLE_SUFFIX_RE = re.compile(r"(은|는|이|가|을|를|에|에서|으로|로|와|과|랑|하고|도|만|까지|부터|보다)$")


def load_profiles(path: Path = PROFILE_PATH) -> dict:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def normalize_text(text: str) -> str:
    return re.sub(r"[\s\-\^·ㆍ_.,!?\"'()]+", "", text or "")


def contains_any(text: str, terms: list[str]) -> list[str]:
    normalized = normalize_text(text)
    hits = []
    for term in terms:
        if not term:
            continue
        if term in text or normalize_text(term) in normalized:
            hits.append(term)
    return list(dict.fromkeys(hits))


def has_object_definition_pattern(sentence: str) -> bool:
    return any(re.search(pattern, sentence or "") for pattern in OBJECT_DEFINITION_PATTERNS)


def strip_particle(term: str) -> str:
    previous = term
    while True:
        current = PARTICLE_SUFFIX_RE.sub("", previous)
        if current == previous:
            return current
        previous = current


def is_target_like_term(term: str, target_word: str) -> bool:
    term_norm = normalize_text(strip_particle(term))
    target_norm = normalize_text(target_word)
    return bool(term_norm and target_norm and term_norm in target_norm)


def is_strong_valid_term(term: str, target_word: str) -> bool:
    cleaned = strip_particle(term)
    if cleaned in GENERIC_VALID_TERMS:
        return False

    term_norm = normalize_text(cleaned)
    target_norm = normalize_text(target_word)
    if term_norm and target_norm and (term_norm in target_norm or target_norm in term_norm):
        return False
    return True


def is_abstract_profile(profile: dict) -> bool:
    text = " ".join(
        str(profile.get(key, ""))
        for key in ["brief_meaning", "excluded_meaning", "reference_example"]
    )
    text += " " + " ".join(profile.get("valid_context_terms", []))
    return any(hint in text for hint in ABSTRACT_DEFINITION_HINTS)


def first_definition(profile: dict, source: str) -> str:
    sources = profile.get("definition_sources", {}) or {}
    items = sources.get(source, []) or []
    if items:
        return re.sub(r"\s+", " ", str(items[0])).strip()
    return ""


def build_incorrect_message(word: str, profile: dict, invalid_hits: list[str]) -> str:
    brief = profile.get("brief_meaning") or "사전 의미"
    hit_text = ", ".join(invalid_hits[:4])
    if hit_text:
        return f"'{word}'은/는 '{brief}'의 뜻인데, 문장에서는 '{hit_text}' 같은 맥락과 연결되어 사전 의미와 맞지 않습니다."
    return f"'{word}'은/는 '{brief}'의 뜻인데, 현재 문장 맥락은 그 의미와 맞지 않습니다."


def validate_meaning_usage(sentence: str, target_word: str | None, profiles: dict | None = None) -> dict:
    profiles = profiles if profiles is not None else load_profiles()
    if not target_word or target_word not in profiles:
        return {
            "correct": True,
            "confidence": 0.0,
            "message": "대상 문화어휘의 의미는 현재 문맥에서 크게 어긋나지 않습니다.",
            "suggestion": None,
            "matched_terms": [],
        }

    profile = profiles[target_word]
    valid_hits = contains_any(sentence, profile.get("valid_context_terms", []))
    strong_valid_hits = [term for term in valid_hits if is_strong_valid_term(term, target_word)]
    invalid_hits = [
        term
        for term in contains_any(sentence, profile.get("invalid_context_terms", []))
        if not is_target_like_term(term, target_word)
    ]
    sentence_without_target = sentence.replace(target_word, "")
    invalid_without_target = [term for term in invalid_hits if term in sentence_without_target]

    clearly_invalid = False
    if invalid_without_target and not strong_valid_hits:
        clearly_invalid = True
    elif invalid_without_target and has_object_definition_pattern(sentence) and is_abstract_profile(profile):
        clearly_invalid = True

    if clearly_invalid:
        suggestion = profile.get("reference_example") or None
        return {
            "correct": False,
            "confidence": 0.86,
            "message": build_incorrect_message(target_word, profile, invalid_hits),
            "suggestion": suggestion,
            "matched_terms": invalid_hits,
            "krdict_definition": first_definition(profile, "krdict"),
            "opendict_definition": first_definition(profile, "opendict"),
        }

    return {
        "correct": True,
        "confidence": 0.62 if valid_hits else 0.35,
        "message": "대상 문화어휘의 의미는 현재 문맥에서 크게 어긋나지 않습니다.",
        "suggestion": None,
        "matched_terms": valid_hits,
        "krdict_definition": first_definition(profile, "krdict"),
        "opendict_definition": first_definition(profile, "opendict"),
    }
