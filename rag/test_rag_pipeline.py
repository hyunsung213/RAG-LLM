import json
import sys
from pathlib import Path

# rag 폴더 내부 파일 import를 위한 경로 추가
sys.path.append(str(Path(__file__).resolve().parent))

from generate_feedback import generate_feedback
from search_rag import search_documents_balanced


def clean_preview(text: str, max_len: int = 120) -> str:
    """
    검색 근거 출력용 미리보기 문자열을 정리합니다.
    """
    if not text:
        return ""

    preview = text.replace("\n", " ").replace("\r", " ").strip()
    preview = " ".join(preview.split())

    if len(preview) > max_len:
        preview = preview[:max_len] + "..."

    return preview


def print_evidence(docs: list[dict]) -> None:
    """
    RAG 검색 결과를 터미널에 보기 좋게 출력합니다.
    """
    print("\n검색 근거:")

    if not docs:
        print("- 검색된 문서가 없습니다.")
        return

    for index, doc in enumerate(docs, start=1):
        word = doc.get("word", "")
        doc_type = doc.get("doc_type", "")
        source = doc.get("source", "")
        distance = doc.get("distance", "")
        content = doc.get("content", "")

        preview = clean_preview(content)

        print(
            f"- [{index}] {word} / {doc_type} / {source} / "
            f"distance={distance}: {preview}"
        )


def print_source_diagnostics(docs: list[dict]) -> None:
    """
    검색 결과에 어떤 출처가 포함되었는지 확인합니다.
    우리말샘(opendict)이 안 들어오는 문제를 바로 확인하기 위한 진단 출력입니다.
    """
    sources = [doc.get("source", "") for doc in docs]
    doc_types = [doc.get("doc_type", "") for doc in docs]

    has_krdict = "krdict" in sources
    has_opendict = "opendict" in sources
    has_spoken = "spoken_example" in doc_types

    print("\n검색 출처 진단:")
    print(f"- 한국어기초사전 krdict 포함 여부: {has_krdict}")
    print(f"- 우리말샘 opendict 포함 여부: {has_opendict}")
    print(f"- 구어체 예문 spoken_example 포함 여부: {has_spoken}")

    if not has_opendict:
        print(
            "- 주의: 우리말샘(opendict) 근거가 검색 결과에 포함되지 않았습니다. "
            "이 경우 search_rag.py에서 opendict를 별도 검색하도록 수정해야 합니다."
        )

    if not has_spoken:
        print(
            "- 주의: 구어체 예문이 검색 결과에 포함되지 않았습니다. "
            "구어체 변환 품질을 높이려면 spoken_example 검색이 포함되어야 합니다."
        )


def print_feedback(feedback: dict) -> None:
    """
    Gemini 또는 fallback 피드백 결과를 출력합니다.
    """
    print("\n피드백:")
    print(json.dumps(feedback, ensure_ascii=False, indent=2))

    spoken = feedback.get("natural_spoken_sentence")
    if spoken:
        print("\n구어체 변환 문장:")
        print(spoken)


def run_once(sentence: str) -> None:
    """
    문장 1개에 대해 RAG 검색 → 근거 출력 → 피드백 생성 → 구어체 문장 출력까지 수행합니다.
    """
    docs = search_documents_balanced(sentence, top_k=8)

    print_evidence(docs)
    print_source_diagnostics(docs)

    feedback = generate_feedback(sentence, docs)
    print_feedback(feedback)


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
            print("Chroma 인덱스, .env 설정, search_rag.py 검색 함수를 확인하세요.", file=sys.stderr)


if __name__ == "__main__":
    main()