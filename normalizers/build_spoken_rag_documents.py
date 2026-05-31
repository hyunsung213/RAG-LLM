import json
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]

INPUT_PATH = ROOT_DIR / "output" / "normalized" / "normalized_spoken_examples_sample_50000.jsonl"
OUTPUT_PATH = ROOT_DIR / "output" / "normalized" / "rag_documents_spoken_sample_50000.jsonl"


def main():
    if not INPUT_PATH.exists():
        print(f"입력 파일이 없습니다: {INPUT_PATH}")
        return

    count = 0

    with INPUT_PATH.open("r", encoding="utf-8") as fin, OUTPUT_PATH.open("w", encoding="utf-8") as fout:
        for line in fin:
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue

            raw_text = obj.get("text", "").strip()
            if not raw_text:
                continue

            doc_id = obj.get("id") or f"spoken_example_{count}"
            content = f"구어체 예문: {raw_text}"

            metadata = obj.get("metadata", {})
            metadata.update({
                "source": obj.get("source", "modu_dialogue_2022"),
                "doc_type": "spoken_example",
                "style": "spoken",
                "purpose": "natural_spoken_sentence_reference"
            })

            rag_doc = {
                "doc_id": doc_id,
                "id": doc_id,
                "doc_type": "spoken_example",
                "word": "",
                "content": content,
                "text": content,
                "metadata": metadata
            }

            fout.write(json.dumps(rag_doc, ensure_ascii=False) + "\n")
            count += 1

    print(f"RAG 구어체 문서 생성 완료: {count}개")
    print(f"저장 위치: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
