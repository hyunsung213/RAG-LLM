from __future__ import annotations

import csv
import hashlib
import html
import json
import re
from pathlib import Path
from typing import Any, Iterable


ROOT_DIR = Path(__file__).resolve().parents[2]
SEED_PATH = ROOT_DIR / "seed_cultural_words.csv"
NORMALIZED_DIR = ROOT_DIR / "output" / "normalized"

NORMALIZED_WORDS_PATH = NORMALIZED_DIR / "normalized_words.jsonl"
NORMALIZED_DEFINITIONS_PATH = NORMALIZED_DIR / "normalized_definitions.jsonl"
NORMALIZED_EXAMPLES_PATH = NORMALIZED_DIR / "normalized_examples.jsonl"
NORMALIZED_EXPRESSIONS_PATH = NORMALIZED_DIR / "normalized_expressions.jsonl"
NORMALIZATION_FAILED_PATH = NORMALIZED_DIR / "normalization_failed.jsonl"
RAG_DOCUMENTS_PATH = NORMALIZED_DIR / "rag_documents.jsonl"


NORMALIZED_OUTPUTS = [
    NORMALIZED_WORDS_PATH,
    NORMALIZED_DEFINITIONS_PATH,
    NORMALIZED_EXAMPLES_PATH,
    NORMALIZED_EXPRESSIONS_PATH,
    NORMALIZATION_FAILED_PATH,
    RAG_DOCUMENTS_PATH,
]


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def init_files(paths: Iterable[Path]) -> None:
    ensure_dir(NORMALIZED_DIR)
    for path in paths:
        path.write_text("", encoding="utf-8")


def append_jsonl(path: Path, data: dict) -> None:
    ensure_dir(path.parent)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(data, ensure_ascii=False) + "\n")


def read_jsonl(path: Path) -> Iterable[dict]:
    if not path.exists():
        return

    with path.open("r", encoding="utf-8-sig") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as exc:
                append_failed(
                    source="jsonl",
                    stage="read_jsonl",
                    reason=f"JSON decode error at line {line_no}: {exc}",
                    record={"path": str(path)},
                )


def load_seed_words(csv_path: Path = SEED_PATH) -> list[dict]:
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def seed_by_word() -> dict[str, dict]:
    return {seed["word"]: seed for seed in load_seed_words()}


def seed_to_word_record(seed: dict) -> dict:
    return {
        "word_id": stable_id("seed_word", seed.get("word")),
        "word": clean_text(seed.get("word")),
        "word_type": clean_text(seed.get("word_type")),
        "pos": clean_text(seed.get("pos")),
        "pronunciation": clean_text(seed.get("pronunciation")),
        "english_title": clean_text(seed.get("english_title")),
        "brief_meaning": clean_text(seed.get("brief_meaning")),
        "excluded_meaning": clean_text(seed.get("excluded_meaning")),
        "example": clean_text(seed.get("example")),
        "spacing_allowed": clean_text(seed.get("spacing_allowed")),
        "difficulty": clean_text(seed.get("difficulty")),
        "tags": split_tags(seed.get("culture_tags")),
        "priority": parse_int(seed.get("priority")),
        "reason": clean_text(seed.get("reason")),
        "source": "seed_cultural_words",
    }


def write_seed_words(reset: bool = False) -> int:
    if reset:
        init_files(NORMALIZED_OUTPUTS)

    count = 0
    for seed in load_seed_words():
        append_jsonl(NORMALIZED_WORDS_PATH, seed_to_word_record(seed))
        count += 1
    return count


def append_failed(source: str, stage: str, reason: str, record: dict | None = None) -> None:
    append_jsonl(
        NORMALIZATION_FAILED_PATH,
        {
            "source": source,
            "stage": stage,
            "reason": reason,
            "record": record or {},
        },
    )


def as_list(value: Any) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        value = json.dumps(value, ensure_ascii=False)
    return html.unescape(str(value)).strip()


def split_tags(value: Any) -> list[str]:
    return [tag for tag in clean_text(value).split("|") if tag]


def parse_int(value: Any) -> int | None:
    try:
        return int(clean_text(value))
    except (TypeError, ValueError):
        return None


def normalize_match_text(value: str) -> str:
    return re.sub(r"[\s\-\^·ㆍ_]+", "", value or "")


def stable_id(*parts: Any) -> str:
    text = "|".join(clean_text(part) for part in parts)
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]


def first_text(data: dict, keys: list[str]) -> str:
    for key in keys:
        if key in data:
            return clean_text(data.get(key))
    return ""


def find_values_by_key(value: Any, target_key: str) -> list[Any]:
    found = []
    if isinstance(value, dict):
        for key, child in value.items():
            if key == target_key:
                found.append(child)
            found.extend(find_values_by_key(child, target_key))
    elif isinstance(value, list):
        for child in value:
            found.extend(find_values_by_key(child, target_key))
    return found


def word_seed_from_record(record: dict, seeds: dict[str, dict]) -> dict:
    seed = record.get("seed")
    if isinstance(seed, dict) and seed.get("word"):
        return seed
    query = clean_text(record.get("query"))
    return seeds.get(query, {"word": query})


def build_definition_record(
    *,
    source: str,
    seed: dict,
    source_word: str,
    source_word_id: str,
    source_sense_id: str,
    pos: str,
    definition: str,
    link: str = "",
    origin: str = "",
    category: str = "",
    source_payload: dict | None = None,
) -> dict:
    seed_word = clean_text(seed.get("word"))
    definition_id = stable_id(source, source_word_id, source_sense_id, definition)
    return {
        "definition_id": definition_id,
        "word_id": stable_id("seed_word", seed_word),
        "source": source,
        "seed_word": seed_word,
        "word": clean_text(source_word) or seed_word,
        "source_word_id": clean_text(source_word_id),
        "source_sense_id": clean_text(source_sense_id),
        "pos": clean_text(pos) or clean_text(seed.get("pos")),
        "pronunciation": clean_text(seed.get("pronunciation")),
        "english_title": clean_text(seed.get("english_title")),
        "brief_meaning": clean_text(seed.get("brief_meaning")),
        "excluded_meaning": clean_text(seed.get("excluded_meaning")),
        "reference_example": clean_text(seed.get("example")),
        "spacing_allowed": clean_text(seed.get("spacing_allowed")),
        "definition": clean_text(definition),
        "origin": clean_text(origin),
        "category": clean_text(category),
        "link": clean_text(link),
        "difficulty": clean_text(seed.get("difficulty")),
        "tags": split_tags(seed.get("culture_tags")),
        "is_seed_exact_match": normalize_match_text(seed_word) == normalize_match_text(source_word),
        "source_payload": source_payload or {},
    }


def build_example_record(
    *,
    source: str,
    definition_id: str,
    seed: dict,
    source_word: str,
    example: str,
    translation: str = "",
    index: int = 1,
    source_payload: dict | None = None,
) -> dict:
    example_text = clean_text(example)
    return {
        "example_id": stable_id(source, definition_id, index, example_text),
        "definition_id": definition_id,
        "word_id": stable_id("seed_word", seed.get("word")),
        "source": source,
        "seed_word": clean_text(seed.get("word")),
        "word": clean_text(source_word) or clean_text(seed.get("word")),
        "example": example_text,
        "translation": clean_text(translation),
        "source_payload": source_payload or {},
    }
