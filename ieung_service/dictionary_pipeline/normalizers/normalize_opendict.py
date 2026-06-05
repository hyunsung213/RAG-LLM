import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.append(str(Path(__file__).resolve().parent))
from common import (
    NORMALIZED_DEFINITIONS_PATH,
    NORMALIZED_EXAMPLES_PATH,
    NORMALIZED_EXPRESSIONS_PATH,
    ROOT_DIR,
    append_failed,
    append_jsonl,
    as_list,
    build_definition_record,
    build_example_record,
    clean_text,
    first_text,
    load_seed_words,
    normalize_match_text,
    stable_id,
    word_seed_from_record,
    write_seed_words,
)


RAW_PATH = ROOT_DIR / "output" / "opendict" / "opendict_raw_results.jsonl"


def extract_items(raw: Any) -> list[dict]:
    if not isinstance(raw, dict):
        return []
    channel = raw.get("channel", {})
    if not isinstance(channel, dict):
        return []
    return [item for item in as_list(channel.get("item")) if isinstance(item, dict)]


def extract_senses(item: dict) -> list[dict]:
    return [sense for sense in as_list(item.get("sense")) if isinstance(sense, dict)]


def extract_examples(sense: dict) -> list[dict]:
    """우리말샘 응답에 용례 필드가 있을 때 예문으로 정규화한다."""
    examples = []
    candidates = []
    for key in ["example", "examples", "usage", "usageExample", "example_info", "exampleInfo"]:
        candidates.extend(as_list(sense.get(key)))

    for candidate in candidates:
        if isinstance(candidate, dict):
            text = first_text(candidate, ["example", "sentence", "text", "usage"])
            translation = first_text(candidate, ["translation", "trans", "meaning"])
        else:
            text = clean_text(candidate)
            translation = ""

        if text:
            examples.append({"example": text, "translation": translation, "raw": candidate})

    return examples


def is_expression_candidate(seed_word: str, source_word: str) -> bool:
    seed_norm = normalize_match_text(seed_word)
    source_norm = normalize_match_text(source_word)
    if not source_word or seed_norm == source_norm:
        return False
    return seed_norm in source_norm or " " in source_word or "-" in source_word


def append_expression_candidate(seed: dict, item: dict, sense: dict, item_index: int, sense_index: int) -> bool:
    seed_word = clean_text(seed.get("word"))
    source_word = clean_text(item.get("word"))
    if not is_expression_candidate(seed_word, source_word):
        return False

    record = {
        "expression_id": stable_id("opendict_expression", seed_word, source_word, sense.get("target_code"), sense_index),
        "source": "opendict",
        "seed_word": seed_word,
        "expression": source_word,
        "pos": clean_text(sense.get("pos")),
        "definition": clean_text(sense.get("definition")),
        "link": clean_text(sense.get("link")),
        "difficulty": clean_text(seed.get("difficulty")),
        "tags": [tag for tag in clean_text(seed.get("culture_tags")).split("|") if tag],
        "source_payload": {
            "item_index": item_index,
            "sense_index": sense_index,
            "target_code": clean_text(sense.get("target_code")),
        },
    }
    append_jsonl(NORMALIZED_EXPRESSIONS_PATH, record)
    return True


def normalize_record(record: dict, seeds: dict[str, dict]) -> tuple[int, int, int]:
    seed = word_seed_from_record(record, seeds)
    raw = record.get("raw", {})
    items = extract_items(raw)
    if not items:
        append_failed("opendict", "extract_items", "item을 찾지 못했습니다.", compact_record(record))
        return 0, 0, 0

    definition_count = 0
    example_count = 0
    expression_count = 0

    for item_index, item in enumerate(items, start=1):
        source_word = clean_text(item.get("word")) or clean_text(seed.get("word"))
        senses = extract_senses(item)
        if not senses:
            append_failed("opendict", "extract_senses", "sense를 찾지 못했습니다.", {"item": item})
            continue

        for sense_index, sense in enumerate(senses, start=1):
            definition = clean_text(sense.get("definition"))
            if not definition:
                append_failed("opendict", "extract_definition", "뜻풀이를 찾지 못했습니다.", {"item": item, "sense": sense})
                continue

            source_sense_id = clean_text(sense.get("target_code")) or clean_text(sense.get("sense_no")) or str(sense_index)
            definition_record = build_definition_record(
                source="opendict",
                seed=seed,
                source_word=source_word,
                source_word_id=stable_id("opendict_word", source_word),
                source_sense_id=source_sense_id,
                pos=clean_text(sense.get("pos")),
                definition=definition,
                link=clean_text(sense.get("link")),
                origin=clean_text(sense.get("origin")),
                category=clean_text(sense.get("cat")),
                source_payload={
                    "item_index": item_index,
                    "sense_index": sense_index,
                    "sense_no": clean_text(sense.get("sense_no")),
                    "type": clean_text(sense.get("type")),
                },
            )
            append_jsonl(NORMALIZED_DEFINITIONS_PATH, definition_record)
            definition_count += 1

            if append_expression_candidate(seed, item, sense, item_index, sense_index):
                expression_count += 1

            for example_index, example in enumerate(extract_examples(sense), start=1):
                example_record = build_example_record(
                    source="opendict",
                    definition_id=definition_record["definition_id"],
                    seed=seed,
                    source_word=source_word,
                    example=example["example"],
                    translation=example.get("translation", ""),
                    index=example_index,
                    source_payload={"raw": example.get("raw", {})},
                )
                append_jsonl(NORMALIZED_EXAMPLES_PATH, example_record)
                example_count += 1

    return definition_count, example_count, expression_count


def compact_record(record: dict) -> dict:
    return {
        "source": record.get("source"),
        "query": record.get("query"),
        "seed": record.get("seed"),
        "raw_keys": list(record.get("raw", {}).keys()) if isinstance(record.get("raw"), dict) else [],
    }


def read_raw(path: Path):
    with path.open("r", encoding="utf-8-sig") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as exc:
                append_failed("opendict", "read_raw", f"JSON decode error at line {line_no}: {exc}", {"path": str(path)})


def main() -> None:
    parser = argparse.ArgumentParser(description="우리말샘 raw JSONL 정규화")
    parser.add_argument("--raw", type=Path, default=RAW_PATH)
    parser.add_argument("--reset", action="store_true", help="기존 normalized 파일을 초기화하고 seed 단어를 다시 씁니다.")
    args = parser.parse_args()

    seed_count = write_seed_words(reset=True) if args.reset else 0
    seeds = {seed["word"]: seed for seed in load_seed_words()}

    stats = {"seed_words": seed_count, "definitions": 0, "examples": 0, "expressions": 0}
    for record in read_raw(args.raw):
        definitions, examples, expressions = normalize_record(record, seeds)
        stats["definitions"] += definitions
        stats["examples"] += examples
        stats["expressions"] += expressions

    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
