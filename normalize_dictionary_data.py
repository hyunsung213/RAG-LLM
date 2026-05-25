import argparse
import hashlib
import html
import json
import re
from pathlib import Path
from typing import Any, Iterable


ROOT_DIR = Path(__file__).resolve().parent
DEFAULT_KRDICT_PATH = ROOT_DIR / "output" / "krdict" / "krdict_raw_results.jsonl"
DEFAULT_OPENDICT_PATH = ROOT_DIR / "output" / "opendict" / "opendict_raw_results.jsonl"
NORMALIZED_DIR = ROOT_DIR / "output" / "normalized"
WORDS_PATH = NORMALIZED_DIR / "normalized_words.jsonl"
DEFINITIONS_PATH = NORMALIZED_DIR / "normalized_definitions.jsonl"
EXAMPLES_PATH = NORMALIZED_DIR / "normalized_examples.jsonl"
RAG_DOCS_PATH = NORMALIZED_DIR / "rag_documents.jsonl"


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def append_jsonl(path: Path, data: dict) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(data, ensure_ascii=False) + "\n")


def reset_output_files(paths: Iterable[Path]) -> None:
    ensure_dir(NORMALIZED_DIR)
    for path in paths:
        path.write_text("", encoding="utf-8")


def read_jsonl(path: Path) -> Iterable[dict]:
    if not path.exists():
        return

    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as exc:
                # 원본 파일 일부가 깨져도 전체 정규화가 중단되지 않도록 한다.
                yield {
                    "source": "unknown",
                    "raw": {"error": {"message": f"JSON decode error at line {line_no}: {exc}"}},
                }


def as_list(value: Any) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def text_or_empty(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return html.unescape(str(value)).strip()


def normalize_lookup_text(value: str) -> str:
    """검색어 비교용으로 사전 표기 하이픈, 공백, 구두점을 가볍게 제거한다."""
    return re.sub(r"[\s\-\^·ㆍ_]+", "", value or "")


def stable_id(*parts: Any) -> str:
    joined = "|".join(text_or_empty(part) for part in parts)
    return hashlib.sha1(joined.encode("utf-8")).hexdigest()[:16]


def parse_priority(seed: dict) -> int | None:
    try:
        return int(seed.get("priority", ""))
    except (TypeError, ValueError):
        return None


def seed_metadata(seed: dict) -> dict:
    tags = [tag for tag in text_or_empty(seed.get("culture_tags")).split("|") if tag]
    return {
        "seed_word": text_or_empty(seed.get("word")),
        "word_type": text_or_empty(seed.get("word_type")),
        "seed_pos": text_or_empty(seed.get("pos")),
        "difficulty": text_or_empty(seed.get("difficulty")),
        "culture_tags": tags,
        "priority": parse_priority(seed),
        "reason": text_or_empty(seed.get("reason")),
    }


def is_error_response(record: dict) -> bool:
    raw = record.get("raw", {})
    return isinstance(raw, dict) and "error" in raw


def extract_opendict_entries(record: dict) -> list[dict]:
    """우리말샘 channel.item[].sense[]를 단어-뜻풀이 단위로 펼친다."""
    raw = record.get("raw", {})
    channel = raw.get("channel", {}) if isinstance(raw, dict) else {}
    items = as_list(channel.get("item"))
    entries = []

    for item_index, item in enumerate(items):
        if not isinstance(item, dict):
            continue

        word = text_or_empty(item.get("word"))
        senses = as_list(item.get("sense"))
        for sense_index, sense in enumerate(senses):
            if not isinstance(sense, dict):
                continue
            entries.append(
                {
                    "source": "opendict",
                    "source_item_index": item_index,
                    "source_sense_index": sense_index,
                    "source_word": word,
                    "source_word_id": stable_id("opendict_word", word),
                    "sense_id": text_or_empty(sense.get("target_code")) or text_or_empty(sense.get("sense_no")) or str(sense_index + 1),
                    "sense_order": text_or_empty(sense.get("sense_no")),
                    "definition": text_or_empty(sense.get("definition")),
                    "pos": text_or_empty(sense.get("pos")),
                    "origin": text_or_empty(sense.get("origin")),
                    "category": text_or_empty(sense.get("cat")),
                    "type": text_or_empty(sense.get("type")),
                    "link": text_or_empty(sense.get("link")),
                    "examples": [],
                    "raw_sense": sense,
                }
            )

    return entries


def extract_krdict_entries(record: dict) -> list[dict]:
    """한국어기초사전 XML 파싱 결과에서 가능한 item/sense/example 경로를 방어적으로 처리한다."""
    raw = record.get("raw", {})
    if not isinstance(raw, dict):
        return []

    items = find_values_by_key(raw, "item")
    entries = []

    for item_index, item in enumerate(flatten_items(items)):
        if not isinstance(item, dict):
            continue

        word = first_text(item, ["word", "lexicalUnit", "vocab", "entry"])
        word_id = first_text(item, ["target_code", "word_no", "wordNo", "id"]) or stable_id("krdict", word, item_index)
        pos = first_text(item, ["pos", "partOfSpeech"])

        senses = find_senses(item)
        if not senses:
            senses = [item]

        for sense_index, sense in enumerate(senses):
            if not isinstance(sense, dict):
                continue

            definition = first_text(sense, ["definition", "senseDefinition", "def"])
            if not definition:
                continue

            entries.append(
                {
                    "source": "krdict",
                    "source_item_index": item_index,
                    "source_sense_index": sense_index,
                    "source_word": word,
                    "source_word_id": word_id,
                    "sense_id": first_text(sense, ["sense_no", "senseNo", "sense_order", "id"]) or str(sense_index + 1),
                    "definition": definition,
                    "pos": first_text(sense, ["pos", "partOfSpeech"]) or pos,
                    "origin": first_text(item, ["origin", "original_language"]),
                    "category": first_text(sense, ["cat", "category"]),
                    "type": first_text(sense, ["type"]),
                    "link": first_text(sense, ["link"]) or first_text(item, ["link"]),
                    "examples": extract_examples(sense),
                    "raw_sense": sense,
                }
            )

    return entries


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


def flatten_items(values: list[Any]) -> list[Any]:
    flattened = []
    for value in values:
        flattened.extend(as_list(value))
    return flattened


def find_senses(item: dict) -> list[dict]:
    for key in ["sense", "senses", "definitionInfo", "senseInfo"]:
        if key in item:
            return [sense for sense in as_list(item.get(key)) if isinstance(sense, dict)]
    return []


def first_text(data: dict, keys: list[str]) -> str:
    for key in keys:
        if key in data:
            return text_or_empty(data.get(key))
    return ""


def extract_examples(sense: dict) -> list[dict]:
    examples = []
    for key in ["example", "examples", "exampleInfo"]:
        for item in as_list(sense.get(key)):
            if isinstance(item, dict):
                example_text = first_text(item, ["example", "sentence", "text"])
                translation = first_text(item, ["translation", "trans"])
            else:
                example_text = text_or_empty(item)
                translation = ""

            if example_text:
                examples.append({"example": example_text, "translation": translation})

    return examples


def extract_entries(record: dict) -> list[dict]:
    if is_error_response(record):
        return []

    source = record.get("source")
    if source == "opendict":
        return extract_opendict_entries(record)
    if source == "krdict":
        return extract_krdict_entries(record)
    return []


def exact_seed_match(seed_word: str, source_word: str) -> bool:
    return normalize_lookup_text(seed_word) == normalize_lookup_text(source_word)


def build_word_record(seed: dict, entry: dict) -> dict:
    meta = seed_metadata(seed)
    source_word = entry["source_word"]
    seed_word = meta["seed_word"]
    word_id = stable_id("word", entry["source"], entry["source_word_id"], source_word, seed_word)

    return {
        "word_id": word_id,
        "canonical_word": seed_word,
        "display_word": source_word or seed_word,
        "normalized_display_word": normalize_lookup_text(source_word or seed_word),
        "source": entry["source"],
        "source_word_id": entry["source_word_id"],
        "pos": entry["pos"] or meta["seed_pos"],
        "origin": entry["origin"],
        "is_seed_exact_match": exact_seed_match(seed_word, source_word),
        "seed": meta,
    }


def build_definition_record(seed: dict, entry: dict, word_id: str) -> dict:
    definition_id = stable_id("definition", word_id, entry["source"], entry["sense_id"], entry["definition"])
    return {
        "definition_id": definition_id,
        "word_id": word_id,
        "source": entry["source"],
        "source_word_id": entry["source_word_id"],
        "source_sense_id": entry["sense_id"],
        "source_sense_order": entry.get("sense_order", ""),
        "definition": entry["definition"],
        "pos": entry["pos"],
        "category": entry["category"],
        "type": entry["type"],
        "link": entry["link"],
        "seed_word": text_or_empty(seed.get("word")),
        "is_seed_exact_match": exact_seed_match(text_or_empty(seed.get("word")), entry["source_word"]),
    }


def build_example_record(entry: dict, word_id: str, definition_id: str, example: dict, index: int) -> dict:
    example_id = stable_id("example", definition_id, index, example.get("example"))
    return {
        "example_id": example_id,
        "definition_id": definition_id,
        "word_id": word_id,
        "source": entry["source"],
        "example": text_or_empty(example.get("example")),
        "translation": text_or_empty(example.get("translation")),
    }


def build_dictionary_rag_document(word: dict, definition: dict, examples: list[dict]) -> dict:
    """향후 culture_context, spoken_example 타입을 추가할 수 있도록 doc_type 기반으로 구성한다."""
    seed = word["seed"]
    example_lines = [f"- 예문: {example['example']}" for example in examples if example.get("example")]
    tags = ", ".join(seed.get("culture_tags", []))
    content_parts = [
        f"표제어: {word['canonical_word']}",
        f"사전 표기: {word['display_word']}",
        f"품사: {definition.get('pos') or word.get('pos')}",
        f"난이도: {seed.get('difficulty')}",
        f"문화 태그: {tags}",
        f"문화어휘 선정 이유: {seed.get('reason')}",
        f"뜻풀이: {definition['definition']}",
    ]
    content_parts.extend(example_lines)

    return {
        "doc_id": stable_id("rag", "dictionary_definition", definition["definition_id"]),
        "doc_type": "dictionary_definition",
        "source": definition["source"],
        "title": f"{word['canonical_word']} - 사전 뜻풀이",
        "content": "\n".join(part for part in content_parts if part),
        "metadata": {
            "word_id": word["word_id"],
            "definition_id": definition["definition_id"],
            "canonical_word": word["canonical_word"],
            "display_word": word["display_word"],
            "seed_word": definition["seed_word"],
            "pos": definition.get("pos") or word.get("pos"),
            "difficulty": seed.get("difficulty"),
            "culture_tags": seed.get("culture_tags", []),
            "priority": seed.get("priority"),
            "link": definition.get("link"),
            "future_doc_types": ["culture_context", "spoken_example"],
        },
    }


def normalize_sources(krdict_path: Path, opendict_path: Path) -> dict:
    reset_output_files([WORDS_PATH, DEFINITIONS_PATH, EXAMPLES_PATH, RAG_DOCS_PATH])

    stats = {
        "input_records": 0,
        "word_records": 0,
        "definition_records": 0,
        "example_records": 0,
        "rag_documents": 0,
        "skipped_error_records": 0,
    }

    seen_words = set()

    for path in [krdict_path, opendict_path]:
        for record in read_jsonl(path):
            stats["input_records"] += 1
            if is_error_response(record):
                stats["skipped_error_records"] += 1
                continue

            seed = record.get("seed", {})
            for entry in extract_entries(record):
                if not entry.get("definition"):
                    continue

                word = build_word_record(seed, entry)
                definition = build_definition_record(seed, entry, word["word_id"])

                if word["word_id"] not in seen_words:
                    append_jsonl(WORDS_PATH, word)
                    seen_words.add(word["word_id"])
                    stats["word_records"] += 1

                append_jsonl(DEFINITIONS_PATH, definition)
                stats["definition_records"] += 1

                example_records = []
                for index, example in enumerate(entry.get("examples", []), start=1):
                    example_record = build_example_record(entry, word["word_id"], definition["definition_id"], example, index)
                    append_jsonl(EXAMPLES_PATH, example_record)
                    example_records.append(example_record)
                    stats["example_records"] += 1

                rag_document = build_dictionary_rag_document(word, definition, example_records)
                append_jsonl(RAG_DOCS_PATH, rag_document)
                stats["rag_documents"] += 1

    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="한국어기초사전/우리말샘 원본 JSONL 정규화")
    parser.add_argument("--krdict", type=Path, default=DEFAULT_KRDICT_PATH)
    parser.add_argument("--opendict", type=Path, default=DEFAULT_OPENDICT_PATH)
    args = parser.parse_args()

    stats = normalize_sources(args.krdict, args.opendict)
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    print(f"normalized output: {NORMALIZED_DIR}")


if __name__ == "__main__":
    main()
