import json
import sys

from generate_feedback import collect_evidence, generate_feedback


def print_dictionary_evidence(docs: list[dict]) -> None:
    print("\n사전 근거:")
    if not docs:
        print("- 검색된 사전 근거가 없습니다.")
        return
    for index, doc in enumerate(docs, start=1):
        preview = " ".join(str(doc.get("content", "")).split())
        print(f"- [{index}] {doc.get('source')} / {doc.get('word')} / {preview[:140]}")


def print_spoken_evidence(spoken_result: dict) -> None:
    print("\n구어체 참고 예문:")
    examples = spoken_result.get("examples", [])
    if not examples:
        print("- 검색된 구어체 예문이 없습니다.")
        return
    for index, example in enumerate(examples, start=1):
        print(
            f"- [{index}] score={example.get('score', 0)} / "
            f"{example.get('text', '')} / reasons={','.join(example.get('reasons', []))}"
        )


def main() -> None:
    print("피드백 파이프라인 테스트입니다. 빈 줄을 입력하면 종료합니다.")
    while True:
        sentence = input("\n문장을 입력하세요: ").strip()
        if not sentence:
            print("종료합니다.")
            break
        try:
            evidence = collect_evidence(sentence)
            print_dictionary_evidence(evidence["dictionary_docs"])
            print_spoken_evidence(evidence["spoken_result"])
            feedback = generate_feedback(sentence)
            print("\n최종 피드백:")
            print(json.dumps(feedback, ensure_ascii=False, indent=2))
        except Exception as exc:
            print(f"[ERROR] 파이프라인 실행 실패: {exc}", file=sys.stderr)


if __name__ == "__main__":
    main()
