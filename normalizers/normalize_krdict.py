import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.append(str(Path(__file__).resolve().parent))
from common import (
    NORMALIZED_DEFINITIONS_PATH,
    NORMALIZED_EXAMPLES_PATH,
    ROOT_DIR,
    append_failed,
    append_jsonl,
    as_list,
    build_definition_record,
    build_example_record,
    clean_text,
    first_text,
    load_seed_words,
    word_seed_from_record,
    write_seed_words,
)


RAW_PATH = ROOT_DIR / "output" / "krdict" / "krdict_raw_results.jsonl"


def extract_items(raw: Any) -> list[dict]:
    if not isinstance(raw, dict):
        return []
    channel = raw.get("channel", {})
    if not isinstance(channel, dict):
        return []
    return [item for item in as_list(channel.get("item")) if isinstance(item, dict)]


def extract_senses(item: dict) -> list[dict]:
    senses = [sense for sense in as_list(item.get("sense")) if isinstance(sense, dict)]
    return senses or [item]


def extract_examples(sense: dict) -> list[dict]:
    examples = []
    candidates = []
    for key in ["example", "examples", "example_info", "exampleInfo"]:
        candidates.extend(as_list(sense.get(key)))

    for candidate in candidates:
        if isinstance(candidate, dict):
            text = first_text(candidate, ["example", "sentence", "text"])
            translation = first_text(candidate, ["translation", "trans", "meaning"])
        else:
            text = clean_text(candidate)
            translation = ""

        if text:
            examples.append({"example": text, "translation": translation, "raw": candidate})

    return examples


def normalize_record(record: dict, seeds: dict[str, dict]) -> tuple[int, int]:
    seed = word_seed_from_record(record, seeds)
    raw = record.get("raw", {})
    items = extract_items(raw)
    if not items:
        append_failed("krdict", "extract_items", "item을 찾지 못했습니다.", compact_record(record))
        return 0, 0

    definition_count = 0
    example_count = 0

    for item_index, item in enumerate(items, start=1):
        source_word = first_text(item, ["word", "lexicalUnit", "entry"]) or clean_text(seed.get("word"))
        source_word_id = first_text(item, ["target_code", "word_no", "wordNo", "id"]) or f"{clean_text(seed.get('word'))}_{item_index}"
        pos = first_text(item, ["pos", "partOfSpeech"])
        link = first_text(item, ["link"])
        origin = first_text(item, ["origin"])

        for sense_index, sense in enumerate(extract_senses(item), start=1):
            definition = first_text(sense, ["definition", "senseDefinition", "def"])
            if not definition:
                append_failed("krdict", "extract_definition", "뜻풀이를 찾지 못했습니다.", {"item": item})
                continue

            sense_id = first_text(sense, ["sense_order", "sense_no", "senseNo", "id"]) or str(sense_index)
            definition_record = build_definition_record(
                source="krdict",
                seed=seed,
                source_word=source_word,
                source_word_id=source_word_id,
                source_sense_id=sense_id,
                pos=pos,
                definition=definition,
                link=link,
                origin=origin,
                source_payload={"item_index": item_index, "sense_index": sense_index},
            )
            append_jsonl(NORMALIZED_DEFINITIONS_PATH, definition_record)
            definition_count += 1

            for example_index, example in enumerate(extract_examples(sense), start=1):
                example_record = build_example_record(
                    source="krdict",
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

    return definition_count, example_count


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
                append_failed("krdict", "read_raw", f"JSON decode error at line {line_no}: {exc}", {"path": str(path)})


def main() -> None:
    parser = argparse.ArgumentParser(description="한국어기초사전 raw JSONL 정규화")
    parser.add_argument("--raw", type=Path, default=RAW_PATH)
    parser.add_argument("--append", action="store_true", help="기존 normalized 파일을 초기화하지 않고 append합니다.")
    args = parser.parse_args()

    # 파이프라인 첫 단계이므로 기본 실행에서는 기존 산출물을 초기화하고 seed 단어를 다시 씁니다.
    seed_count = write_seed_words(reset=not args.append)
    seeds = {seed["word"]: seed for seed in load_seed_words()}

    stats = {"seed_words": seed_count, "definitions": 0, "examples": 0}
    for record in read_raw(args.raw):
        definitions, examples = normalize_record(record, seeds)
        stats["definitions"] += definitions
        stats["examples"] += examples

    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
