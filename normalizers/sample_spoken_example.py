import json
import re
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]

INPUT_PATH = ROOT_DIR / "output" / "normalized" / "normalized_spoken_examples.jsonl"
OUTPUT_PATH = ROOT_DIR / "output" / "normalized" / "normalized_spoken_examples_sample_50000.jsonl"

MAX_COUNT = 50000


def is_good_example(text: str) -> bool:
    text = text.strip()
    lower_text = text.lower()

    if len(text) < 8:
        return False

    if len(text) > 80:
        return False

    # name1, name2, name3, name1랑, name2는 같은 익명화 토큰 제거
    if re.search(r"name\d+", lower_text):
        return False

    # 다른 익명화 토큰도 같이 제거
    if re.search(r"(account|phone|email|address|place|company|organization|date|time)\d+", lower_text):
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
    count = 0
    seen = set()

    with INPUT_PATH.open("r", encoding="utf-8") as fin, OUTPUT_PATH.open("w", encoding="utf-8") as fout:
        for line in fin:
            obj = json.loads(line)
            text = obj.get("text", "").strip()

            if not is_good_example(text):
                continue

            if text in seen:
                continue

            seen.add(text)

            obj["text"] = text
            obj["metadata"]["sampled"] = True

            fout.write(json.dumps(obj, ensure_ascii=False) + "\n")
            count += 1

            if count >= MAX_COUNT:
                break

    print(f"샘플 저장 완료: {count}개")
    print(f"저장 위치: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()