import json
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]

INPUT_FILES = [
    ROOT_DIR / "output" / "validation" / "rag_documents_accepted.jsonl",
    ROOT_DIR / "output" / "normalized" / "rag_documents_spoken_sample_50000.jsonl",
]

OUTPUT_FILE = ROOT_DIR / "output" / "normalized" / "rag_documents_combined.jsonl"


def read_jsonl(path: Path):
    if not path.exists():
        print(f"[WARN] 파일 없음: {path}")
        return

    with path.open("r", encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def normalize_doc(doc: dict) -> dict | None:
    doc_id = doc.get("doc_id") or doc.get("id")
    content = doc.get("content") or doc.get("text")

    if not doc_id or not content:
        return None

    metadata = doc.get("metadata") or {}

    return {
        "doc_id": str(doc_id),
        "doc_type": str(doc.get("doc_type") or metadata.get("doc_type") or ""),
        "word": str(doc.get("word") or metadata.get("word") or ""),
        "content": str(content),
        "text": str(doc.get("text") or content),
        "metadata": metadata,
    }


def main():
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    total = 0
    written = 0
    seen_ids = set()

    with OUTPUT_FILE.open("w", encoding="utf-8") as out:
        for input_file in INPUT_FILES:
            for doc in read_jsonl(input_file):
                total += 1
                normalized = normalize_doc(doc)

                if normalized is None:
                    continue

                if normalized["doc_id"] in seen_ids:
                    continue

                seen_ids.add(normalized["doc_id"])
                out.write(json.dumps(normalized, ensure_ascii=False) + "\n")
                written += 1

    print(f"읽은 문서 수: {total}")
    print(f"저장 문서 수: {written}")
    print(f"저장 위치: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()