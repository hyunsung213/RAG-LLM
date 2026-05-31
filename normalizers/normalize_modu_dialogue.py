import json
import re
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]

RAW_DIR = ROOT_DIR / "output" / "modu" / "raw"
OUTPUT_DIR = ROOT_DIR / "output" / "normalized"
OUTPUT_PATH = OUTPUT_DIR / "normalized_spoken_examples.jsonl"


TEXT_KEYS = [
    "form",
    "original_form",
    "text",
    "sentence",
    "utterance",
    "content",
]


def load_json(path: Path):
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def clean_text(text: str) -> str:
    if not text:
        return ""

    text = str(text)
    text = re.sub(r"\s+", " ", text).strip()

    # 일부 말뭉치 주석 기호 제거
    text = re.sub(r"\{[^}]*\}", "", text)
    text = re.sub(r"\s+", " ", text).strip()

    return text


def extract_utterance_text(utterance) -> str:
    """
    utterance 객체에서 실제 발화문을 꺼냅니다.
    국립국어원 구어 말뭉치는 보통 'form' 키에 발화문이 들어 있습니다.
    다만 데이터셋 버전에 따라 키 이름이 다를 수 있어 여러 후보를 확인합니다.
    """
    if isinstance(utterance, str):
        return utterance

    if not isinstance(utterance, dict):
        return ""

    for key in TEXT_KEYS:
        value = utterance.get(key)
        if isinstance(value, str) and value.strip():
            return value

    return ""


def is_valid_spoken_text(text: str) -> bool:
    """
    RAG에 넣기 애매한 너무 짧은 문장, 기호 위주 문장, URL 등을 제거합니다.
    """
    if not text:
        return False

    if len(text) < 5:
        return False

    if len(text) > 160:
        return False

    if re.search(r"https?://|www\.", text):
        return False

    hangul_count = len(re.findall(r"[가-힣]", text))
    if hangul_count < 3:
        return False

    # 한글 비율이 너무 낮으면 잡음일 가능성이 큼
    if hangul_count / max(len(text), 1) < 0.25:
        return False

    return True


def iter_dialogue_records(json_path: Path):
    data = load_json(json_path)

    corpus_id = data.get("id", json_path.stem)
    global_metadata = data.get("metadata", {})
    category = global_metadata.get("category", "")

    documents = data.get("document", [])
    if not isinstance(documents, list):
        return

    for doc in documents:
        if not isinstance(doc, dict):
            continue

        doc_id = doc.get("id", "")
        doc_metadata = doc.get("metadata", {})
        utterances = doc.get("utterance", [])

        if not isinstance(utterances, list):
            continue

        for idx, utterance in enumerate(utterances):
            raw_text = extract_utterance_text(utterance)
            text = clean_text(raw_text)

            if not is_valid_spoken_text(text):
                continue

            if isinstance(utterance, dict):
                utterance_id = utterance.get("id", f"{doc_id}.{idx}")
                speaker_id = utterance.get("speaker_id") or utterance.get("speaker") or ""
            else:
                utterance_id = f"{doc_id}.{idx}"
                speaker_id = ""

            record_id = f"modu_dialogue_{corpus_id}_{doc_id}_{utterance_id}_{idx}"

            yield {
                "id": record_id,
                "source": "modu_dialogue_2022",
                "doc_type": "spoken_example",
                "text": text,
                "metadata": {
                    "corpus_id": corpus_id,
                    "document_id": doc_id,
                    "utterance_id": utterance_id,
                    "speaker_id": speaker_id,
                    "category": category,
                    "document_category": doc_metadata.get("category", ""),
                    "raw_file": str(json_path.relative_to(ROOT_DIR)),
                    "style": "spoken",
                },
            }


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    json_files = sorted(RAW_DIR.rglob("*.json"))

    if not json_files:
        print(f"JSON 파일을 찾지 못했습니다: {RAW_DIR}")
        return

    seen_texts = set()
    total_count = 0

    with OUTPUT_PATH.open("w", encoding="utf-8") as out:
        for json_path in json_files:
            try:
                for record in iter_dialogue_records(json_path):
                    text = record["text"]

                    # 완전히 같은 발화문은 중복 제거
                    if text in seen_texts:
                        continue

                    seen_texts.add(text)
                    out.write(json.dumps(record, ensure_ascii=False) + "\n")
                    total_count += 1

            except Exception as e:
                print(f"[오류] {json_path}: {e}")

    print(f"처리한 JSON 파일 수: {len(json_files)}")
    print(f"추출한 구어체 예문 수: {total_count}")
    print(f"저장 위치: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()