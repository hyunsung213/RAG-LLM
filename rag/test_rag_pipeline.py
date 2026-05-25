import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent))
from generate_feedback import generate_feedback
from search_rag import search_documents


def print_evidence(docs: list[dict]) -> None:
    print("\n검색 근거:")
    if not docs:
        print("- 검색된 문서가 없습니다.")
        return

    for index, doc in enumerate(docs, start=1):
        preview = (doc.get("content") or "").replace("\n", " ")[:120]
        print(
            f"- [{index}] {doc.get('word', '')} / {doc.get('doc_type', '')} / "
            f"{doc.get('source', '')} / distance={doc.get('distance')}: {preview}"
        )


def run_once(sentence: str) -> None:
    docs = search_documents(sentence, top_k=5)
    print_evidence(docs)
    feedback = generate_feedback(sentence, docs)
    print("\n피드백:")
    print(json.dumps(feedback, ensure_ascii=False, indent=2))


def main() -> None:
    print("이응 RAG 파이프라인 테스트입니다. 빈 줄을 입력하면 종료합니다.")
    while True:
        sentence = input("\n문장을 입력하세요: ").strip()
        if not sentence:
            print("종료합니다.")
            break

        try:
            run_once(sentence)
        except Exception as exc:
            print(f"[ERROR] 파이프라인 실행 실패: {exc}", file=sys.stderr)
            print("Chroma 인덱스와 .env 설정을 확인하세요.", file=sys.stderr)


if __name__ == "__main__":
    main()
