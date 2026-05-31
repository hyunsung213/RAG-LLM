import json
import re
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]

INPUT_PATH = ROOT_DIR / "output" / "normalized" / "normalized_spoken_examples.jsonl"
OUTPUT_PATH = ROOT_DIR / "output" / "normalized" / "normalized_spoken_examples_sample_50000.jsonl"

MAX_COUNT = 50000

# name1, name2, name3, account1, place2 같은 익명화 토큰 제거
ANON_TOKEN_RE = re.compile(
    r"(name|account|phone|email|address|place|company|organization|date|time|person|loc|url)\d+",
    re.IGNORECASE
)


def is_good_example(text: str) -> bool:
    text = text.strip()

    if len(text) < 8:
        return False

    if len(text) > 80:
        return False

    # 익명화 토큰이 포함된 문장은 제외
    if ANON_TOKEN_RE.search(text):
        return False

    # 깨진 문자 제거
    if "�" in text or "???" in text:
        return False

    # 한글이 너무 적은 문장 제거
    hangul_count = len(re.findall(r"[가-힣]", text))
    if hangul_count < 5:
        return False

    # 한글 비율이 너무 낮으면 잡음 가능성이 큼
    if hangul_count / max(len(text), 1) < 0.4:
        return False

    return True


def main():
    if not INPUT_PATH.exists():
        print(f"입력 파일이 없습니다: {INPUT_PATH}")
        return

    count = 0
    seen = set()

    with INPUT_PATH.open("r", encoding="utf-8") as fin, OUTPUT_PATH.open("w", encoding="utf-8") as fout:
        for line in fin:
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue

            text = obj.get("text", "").strip()

            if not is_good_example(text):
                continue

            if text in seen:
                continue

            seen.add(text)

            obj["text"] = text
            obj.setdefault("metadata", {})
            obj["metadata"]["sampled"] = True
            obj["metadata"]["filter_version"] = "remove_anonymized_tokens_v2"

            fout.write(json.dumps(obj, ensure_ascii=False) + "\n")
            count += 1

            if count >= MAX_COUNT:
                break

    print(f"샘플 저장 완료: {count}개")
    print(f"저장 위치: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
