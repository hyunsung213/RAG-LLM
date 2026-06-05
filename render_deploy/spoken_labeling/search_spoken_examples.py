from __future__ import annotations

import json
import re
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_INDEX_PATH = ROOT_DIR / "output" / "normalized" / "spoken_lookup_index.json"
DEFAULT_CONFIG_PATH = ROOT_DIR / "spoken_search_config.json"


TOKEN_RE = re.compile(r"[가-힣A-Za-z0-9]+")


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def extract_keywords(sentence: str, stopwords: set[str]) -> list[str]:
    keywords = []
    for token in TOKEN_RE.findall((sentence or "").lower()):
        if len(token) < 2:
            continue
        if token in stopwords:
            continue
        if token not in keywords:
            keywords.append(token)
    return keywords[:6]


def contains_any_patterns(text: str, patterns: list[str]) -> bool:
    for pattern in patterns:
        if not pattern:
            continue
        if pattern in text:
            return True
        if pattern.endswith("다") and pattern[:-1] and pattern[:-1] in text:
            return True
    return False


def contains_related_pattern(text: str, target_word: str, patterns: list[str]) -> bool:
    for pattern in patterns:
        if not pattern:
            continue
        variants = [pattern]
        if pattern.endswith("다") and pattern[:-1]:
            variants.append(pattern[:-1])

        for variant in variants:
            if len(target_word) == 1:
                if re.search(rf"(^|[^가-힣A-Za-z0-9]){re.escape(variant)}", text):
                    return True
            elif variant in text:
                return True
    return False


def contains_target_word(text: str, target_word: str, related_patterns: dict[str, list[str]]) -> bool:
    if not target_word:
        return False

    patterns = related_patterns.get(target_word, [])
    if contains_related_pattern(text, target_word, patterns):
        return True

    if len(target_word) >= 2:
        return target_word in text
    return False


def score_example(
    example: dict,
    *,
    target_word: str | None,
    keywords: list[str],
    config: dict,
) -> tuple[int, list[str]]:
    score_rules = config.get("score_rules", {})
    length_rules = config.get("length_rules", {})
    related_patterns = config.get("related_patterns", {})
    category_preferences = config.get("category_preferences", [])
    relation_preferences = config.get("relation_preferences", [])

    text = str(example.get("text", ""))
    category = str(example.get("category", ""))
    relation = str(example.get("relation", ""))
    text_len = len(text)

    score = 0
    reasons = []

    if target_word and contains_target_word(text, target_word, related_patterns):
        score += int(score_rules.get("target_word_exact", 6))
        reasons.append("target_word_exact")

    if target_word and contains_related_pattern(text, target_word, related_patterns.get(target_word, [])):
        score += int(score_rules.get("related_pattern", 4))
        reasons.append("related_pattern")

    keyword_matches = [keyword for keyword in keywords if keyword and keyword in text.lower()]
    if keyword_matches:
        score += int(score_rules.get("keyword_match", 2)) * len(keyword_matches)
        reasons.append("keyword_match")

    ideal_min = int(length_rules.get("ideal_min", 8))
    ideal_max = int(length_rules.get("ideal_max", 35))
    soft_max = int(length_rules.get("soft_max", 60))

    if ideal_min <= text_len <= ideal_max:
        score += int(score_rules.get("ideal_length", 2))
        reasons.append("ideal_length")
    elif text_len > soft_max:
        score += int(score_rules.get("too_long", -3))
        reasons.append("too_long")

    if any(preferred in category for preferred in category_preferences):
        score += int(score_rules.get("daily_conversation_category", 1))
        reasons.append("daily_conversation_category")

    if any(preferred in relation for preferred in relation_preferences):
        score += int(score_rules.get("friend_or_colleague_relation", 1))
        reasons.append("friend_or_colleague_relation")

    if "<NAME>" in text:
        score += int(score_rules.get("contains_name_placeholder", -2))
        reasons.append("contains_name_placeholder")

    if text_len > 45 and text.count(" ") > 8:
        score += int(score_rules.get("monologue_like", -2))
        reasons.append("monologue_like")

    return score, reasons


def dedupe_examples(examples: list[dict]) -> list[dict]:
    seen = set()
    unique = []
    for example in examples:
        key = re.sub(r"\s+", " ", str(example.get("text", "")).strip().lower())
        if key in seen:
            continue
        seen.add(key)
        unique.append(example)
    return unique


def search_spoken_examples(
    sentence: str,
    target_word: str | None = None,
    index_path: Path = DEFAULT_INDEX_PATH,
    config_path: Path = DEFAULT_CONFIG_PATH,
    top_k: int = 5,
) -> dict:
    index = load_json(index_path)
    config = load_json(config_path)

    stopwords = set(config.get("stopwords", []))
    candidate_limits = config.get("candidate_limits", {})
    keywords = extract_keywords(sentence, stopwords)

    candidates = []
    if target_word:
        candidates.extend(index.get("target_word_index", {}).get(target_word, [])[: int(candidate_limits.get("target_word", 120))])

    general_pool = index.get("general_examples", [])[: int(candidate_limits.get("general_pool", 120))]
    category_pool = []
    relation_pool = []
    for items in index.get("category_index", {}).values():
        category_pool.extend(items[: int(candidate_limits.get("category", 40))])
    for items in index.get("relation_index", {}).values():
        relation_pool.extend(items[: int(candidate_limits.get("relation", 40))])

    candidates.extend(general_pool)
    candidates.extend(category_pool)
    candidates.extend(relation_pool)
    candidates.extend(index.get("fallback_examples", [])[: int(candidate_limits.get("fallback", 30))])

    scored = []
    for example in dedupe_examples(candidates):
        score, reasons = score_example(example, target_word=target_word, keywords=keywords, config=config)
        if score <= 0:
            continue
        enriched = dict(example)
        enriched["score"] = score
        enriched["reasons"] = reasons
        scored.append(enriched)

    scored.sort(key=lambda item: (-int(item.get("score", 0)), len(str(item.get("text", "")))))

    return {
        "query": sentence,
        "target_word": target_word or "",
        "keywords": keywords,
        "examples": scored[:top_k],
    }
