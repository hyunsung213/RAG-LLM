import argparse
import json
import random
import re
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_INPUT_PATH = ROOT_DIR / "output" / "normalized" / "spoken_reference_dataset.jsonl"
DEFAULT_CONFIG_PATH = ROOT_DIR / "spoken_search_config.json"
DEFAULT_OUTPUT_PATH = ROOT_DIR / "output" / "normalized" / "spoken_lookup_index.json"
DEFAULT_STATS_PATH = ROOT_DIR / "output" / "normalized" / "spoken_lookup_index_stats.json"


TOKEN_RE = re.compile(r"[가-힣A-Za-z0-9]+")
NORMALIZE_MATCH_RE = re.compile(r"[\s\-\^·ㆍ_]+")


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def normalize_match_text(text: str) -> str:
    return NORMALIZE_MATCH_RE.sub("", text or "")


def read_jsonl(path: Path):
    with path.open("r", encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def tokenize(text: str, stopwords: set[str]) -> list[str]:
    tokens = []
    for token in TOKEN_RE.findall((text or "").lower()):
        if len(token) < 2:
            continue
        if token in stopwords:
            continue
        tokens.append(token)
    return tokens


def compact_example(record: dict) -> dict:
    return {
        "id": record.get("id", ""),
        "text": record.get("text", ""),
        "source": record.get("source", ""),
        "year": record.get("year", ""),
        "topic": record.get("topic", ""),
        "category": record.get("category", ""),
        "relation": record.get("relation", ""),
    }


def contains_any_patterns(text: str, patterns: list[str]) -> bool:
    normalized_text = normalize_match_text(text)
    for pattern in patterns:
        if not pattern:
            continue
        if pattern in text:
            return True
        if normalize_match_text(pattern) in normalized_text:
            return True
        if pattern.endswith("다") and pattern[:-1] and pattern[:-1] in text:
            return True
    return False


def contains_related_pattern(text: str, target_word: str, patterns: list[str]) -> bool:
    normalized_text = normalize_match_text(text)
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
            elif variant in text or normalize_match_text(variant) in normalized_text:
                return True
    return False


def contains_target_word(text: str, target_word: str, related_patterns: dict[str, list[str]]) -> bool:
    if not target_word:
        return False

    patterns = related_patterns.get(target_word, [])
    if contains_related_pattern(text, target_word, patterns):
        return True

    if len(target_word) >= 2:
        return target_word in text or normalize_match_text(target_word) in normalize_match_text(text)
    return False


def append_limited(bucket: dict, key: str, value: dict, limit: int) -> None:
    items = bucket.setdefault(key, [])
    if len(items) < limit:
        items.append(value)


def build_lookup_index(input_path: Path, config_path: Path, output_path: Path, stats_path: Path) -> dict:
    config = load_json(config_path)
    build_config = config.get("build", {})
    stopwords = set(config.get("stopwords", []))
    target_words = config.get("target_words", [])
    related_patterns = config.get("related_patterns", {})
    category_preferences = config.get("category_preferences", [])
    relation_preferences = config.get("relation_preferences", [])

    random.seed(42)

    index = {
        "target_word_index": {},
        "category_index": {},
        "relation_index": {},
        "general_examples": [],
        "fallback_examples": [],
        "config_snapshot": config,
    }

    max_general_examples = int(build_config.get("max_general_examples", 80000))
    per_target_word_limit = int(build_config.get("per_target_word_limit", 200))
    per_category_limit = int(build_config.get("per_category_limit", 120))
    per_relation_limit = int(build_config.get("per_relation_limit", 120))
    fallback_limit = int(build_config.get("fallback_limit", 300))
    min_text_len = int(build_config.get("min_text_len", 8))
    max_text_len = int(build_config.get("max_text_len", 60))
    allowed_sources = set(build_config.get("allowed_sources", ["nikl_dialogue", "nikl_om"]))

    stats = {
        "input_rows": 0,
        "indexed_general_examples": 0,
        "indexed_target_examples": 0,
        "indexed_category_examples": 0,
        "indexed_relation_examples": 0,
        "fallback_examples": 0,
        "output_path": str(output_path),
    }

    for record in read_jsonl(input_path):
        stats["input_rows"] += 1
        text = str(record.get("text", "")).strip()
        source = str(record.get("source", ""))
        if source not in allowed_sources:
            continue
        if len(text) < min_text_len or len(text) > max_text_len:
            continue

        example = compact_example(record)
        matched_target = False
        for target_word in target_words:
            if contains_target_word(text, target_word, related_patterns):
                append_limited(index["target_word_index"], target_word, example, per_target_word_limit)
                matched_target = True
                stats["indexed_target_examples"] += 1

        category = str(record.get("category", ""))
        relation = str(record.get("relation", ""))

        for preferred_category in category_preferences:
            if preferred_category in category:
                append_limited(index["category_index"], preferred_category, example, per_category_limit)
                stats["indexed_category_examples"] += 1
                break

        for preferred_relation in relation_preferences:
            if preferred_relation in relation:
                append_limited(index["relation_index"], preferred_relation, example, per_relation_limit)
                stats["indexed_relation_examples"] += 1
                break

        if matched_target:
            if len(index["fallback_examples"]) < fallback_limit:
                index["fallback_examples"].append(example)
                stats["fallback_examples"] = len(index["fallback_examples"])
            continue

        if len(index["general_examples"]) < max_general_examples:
            index["general_examples"].append(example)
            stats["indexed_general_examples"] += 1
            continue

        # Reservoir sampling for a stable but diverse general pool.
        replace_at = random.randint(0, stats["input_rows"] - 1)
        if replace_at < max_general_examples:
            index["general_examples"][replace_at] = example

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(index, ensure_ascii=False), encoding="utf-8")
    stats_path.write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="구어체 예문 검색용 경량 인덱스 생성")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT_PATH)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--stats", type=Path, default=DEFAULT_STATS_PATH)
    args = parser.parse_args()

    stats = build_lookup_index(args.input, args.config, args.output, args.stats)
    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
