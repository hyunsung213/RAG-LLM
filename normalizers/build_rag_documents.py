import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent))
from common import (
    NORMALIZED_DEFINITIONS_PATH,
    NORMALIZED_EXAMPLES_PATH,
    RAG_DOCUMENTS_PATH,
    append_failed,
    append_jsonl,
    clean_text,
    init_files,
    read_jsonl,
    stable_id,
)


def load_examples_by_definition(path: Path) -> dict[str, list[dict]]:
    examples_by_definition: dict[str, list[dict]] = defaultdict(list)
    for example in read_jsonl(path):
        definition_id = clean_text(example.get("definition_id"))
        if definition_id:
            examples_by_definition[definition_id].append(example)
    return examples_by_definition


def build_word_definition_doc(definition: dict, examples: list[dict], index: int) -> dict:
    word = clean_text(definition.get("seed_word")) or clean_text(definition.get("word"))
    pos = clean_text(definition.get("pos"))
    definition_text = clean_text(definition.get("definition"))
    example_lines = [clean_text(example.get("example")) for example in examples if clean_text(example.get("example"))]
    example_block = "\n".join(f"예문: {line}" for line in example_lines)

    content_parts = [
        f"단어: {word}",
        f"품사: {pos}",
        f"뜻: {definition_text}",
    ]
    if example_block:
        content_parts.append(example_block)

    source = clean_text(definition.get("source"))
    return {
        "doc_id": f"{source}_{word}_{index}",
        "doc_type": "word_definition",
        "word": word,
        "content": "\n".join(content_parts),
        "metadata": {
            "source": source,
            "pos": pos,
            "difficulty": clean_text(definition.get("difficulty")),
            "tags": definition.get("tags", []),
            "definition_id": clean_text(definition.get("definition_id")),
            "source_word": clean_text(definition.get("word")),
            "source_word_id": clean_text(definition.get("source_word_id")),
            "source_sense_id": clean_text(definition.get("source_sense_id")),
            "link": clean_text(definition.get("link")),
        },
    }


def build_rag_documents(definitions_path: Path, examples_path: Path, reset: bool = True) -> dict:
    if reset:
        init_files([RAG_DOCUMENTS_PATH])

    examples_by_definition = load_examples_by_definition(examples_path)
    stats = {"word_definition": 0, "skipped": 0}

    for index, definition in enumerate(read_jsonl(definitions_path), start=1):
        if not clean_text(definition.get("definition")):
            append_failed("rag", "build_word_definition", "definition이 비어 있습니다.", definition)
            stats["skipped"] += 1
            continue

        doc = build_word_definition_doc(
            definition=definition,
            examples=examples_by_definition.get(clean_text(definition.get("definition_id")), []),
            index=index,
        )
        append_jsonl(RAG_DOCUMENTS_PATH, doc)
        stats["word_definition"] += 1

    # 이후 KCISA는 culture_context, 모두의 말뭉치는 spoken_example 빌더를 여기에 추가한다.
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="정규화된 사전 데이터를 RAG 문서로 변환")
    parser.add_argument("--definitions", type=Path, default=NORMALIZED_DEFINITIONS_PATH)
    parser.add_argument("--examples", type=Path, default=NORMALIZED_EXAMPLES_PATH)
    parser.add_argument("--append", action="store_true", help="기존 rag_documents.jsonl을 초기화하지 않고 append합니다.")
    args = parser.parse_args()

    stats = build_rag_documents(args.definitions, args.examples, reset=not args.append)
    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
