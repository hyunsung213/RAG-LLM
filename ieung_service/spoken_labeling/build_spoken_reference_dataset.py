import argparse
import csv
import hashlib
import json
import re
from pathlib import Path
from typing import Iterable, Optional

ROOT_DIR = Path(__file__).resolve().parents[1]


DEFAULT_RAW_DIR = ROOT_DIR / "raw_data"
DEFAULT_OUTPUT_PATH = ROOT_DIR / "output" / "normalized" / "spoken_reference_dataset.jsonl"
DEFAULT_STATS_PATH = ROOT_DIR / "output" / "normalized" / "spoken_reference_dataset_stats.json"


URL_RE = re.compile(r"https?://|www\.", re.IGNORECASE)
SPACE_RE = re.compile(r"\s+")
ANON_NAME_RE = re.compile(r"&?name\d+&?", re.IGNORECASE)
META_TOKEN_RE = re.compile(r"\{[^}]*\}")
ONLY_SYMBOL_RE = re.compile(r"^[\W_]+$", re.UNICODE)
ONLY_REACTION_RE = re.compile(r"^[ㅋㅎㅠㅜㄷㅂㅇ~!?.\s]+$", re.IGNORECASE)


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def stable_id(*parts: str) -> str:
    joined = "|".join(str(part or "").strip() for part in parts)
    return hashlib.sha1(joined.encode("utf-8")).hexdigest()[:16]


def clean_text(text: str) -> str:
    text = str(text or "")
    text = text.replace("\r", " ").replace("\n", " ")
    text = ANON_NAME_RE.sub("<NAME>", text)
    text = SPACE_RE.sub(" ", text).strip()
    return text


def to_hangul_count(text: str) -> int:
    return len(re.findall(r"[가-힣]", text))


def to_ascii_word_count(text: str) -> int:
    return len(re.findall(r"[A-Za-z0-9]", text))


def is_noise_text(text: str, original_text: str, min_len: int, max_len: int) -> tuple[bool, str]:
    if not text:
        return True, "empty_text"

    if len(text) < min_len:
        return True, "too_short"

    if len(text) > max_len:
        return True, "too_long"

    if URL_RE.search(text):
        return True, "contains_url"

    if ONLY_SYMBOL_RE.match(text):
        return True, "only_symbols"

    if ONLY_REACTION_RE.match(text):
        return True, "only_reaction_chars"

    if to_hangul_count(text) < 2 and to_ascii_word_count(text) < 4:
        return True, "too_little_language_content"

    # form이 비고 original_form이 메타 토큰만 있는 경우(emoji/share 등) 제거
    original_stripped = SPACE_RE.sub("", str(original_text or ""))
    if META_TOKEN_RE.sub("", original_stripped) == "":
        return True, "meta_token_only"

    return False, ""


def read_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def iter_json_utterances(path: Path) -> Iterable[dict]:
    data = read_json(path)
    file_id = str(data.get("id", path.stem))
    metadata = data.get("metadata", {}) if isinstance(data.get("metadata"), dict) else {}
    year = str(metadata.get("year", ""))
    category = str(metadata.get("category", ""))

    for doc in data.get("document", []) or []:
        if not isinstance(doc, dict):
            continue
        doc_id = str(doc.get("id", ""))
        doc_meta = doc.get("metadata", {}) if isinstance(doc.get("metadata"), dict) else {}
        topic = str(doc_meta.get("topic", ""))
        setting = doc_meta.get("setting", {}) if isinstance(doc_meta.get("setting"), dict) else {}
        relation = str(setting.get("relation", ""))

        for utt in doc.get("utterance", []) or []:
            if not isinstance(utt, dict):
                continue

            utt_id = str(utt.get("id", ""))
            form = str(utt.get("form", ""))
            original_form = str(utt.get("original_form", ""))
            speaker_id = str(utt.get("speaker_id", ""))
            time = str(utt.get("time", ""))

            if not time:
                start = utt.get("start")
                end = utt.get("end")
                if start is not None and end is not None:
                    time = f"{start}-{end}"

            source = "nikl_om" if "OM" in path.as_posix().upper() else "nikl_dialogue"
            text = form if str(form).strip() else original_form

            yield {
                "file_id": file_id,
                "source": source,
                "year": year,
                "doc_id": doc_id,
                "utt_id": utt_id,
                "speaker_id": speaker_id,
                "text": text,
                "original_text": original_form or form,
                "topic": topic,
                "category": category,
                "relation": relation,
                "time": time,
                "raw_file": str(path.relative_to(ROOT_DIR)),
            }


def iter_csv_rows(path: Path) -> Iterable[dict]:
    encodings = ["utf-8-sig", "cp949", "euc-kr"]
    last_error: Optional[Exception] = None
    for enc in encodings:
        try:
            with path.open("r", encoding=enc, errors="replace", newline="") as f:
                # 일부 원본 CSV에는 NUL 문자가 섞여 있어 csv 모듈이 바로 중단된다.
                cleaned_lines = (line.replace("\x00", "") for line in f)
                reader = csv.DictReader(cleaned_lines)
                for row in reader:
                    yield row
            return
        except Exception as exc:  # pragma: no cover
            last_error = exc
            continue
    raise RuntimeError(f"CSV 파일 인코딩을 읽지 못했습니다: {path} / {last_error}")


def iter_csv_utterances(path: Path) -> Iterable[dict]:
    for row in iter_csv_rows(path):
        text = str(row.get("form", "")).strip() or str(row.get("original_form", ""))
        yield {
            "file_id": str(row.get("file_id", path.stem)),
            "source": "nikl_om",
            "year": str(row.get("date", ""))[:4],
            "doc_id": str(row.get("doc_id", "")),
            "utt_id": str(row.get("sent_id", "")),
            "speaker_id": str(row.get("speaker", "")),
            "text": text,
            "original_text": str(row.get("original_form", text)),
            "topic": str(row.get("topic", "")),
            "category": str(row.get("category", "")),
            "relation": str(row.get("setting", "")),
            "time": str(row.get("time", "")),
            "raw_file": str(path.relative_to(ROOT_DIR)),
        }


def schema_unify(record: dict) -> dict:
    text = clean_text(record.get("text", ""))
    original_text = clean_text(record.get("original_text", ""))
    source = str(record.get("source", ""))
    file_id = str(record.get("file_id", ""))
    doc_id = str(record.get("doc_id", ""))
    utt_id = str(record.get("utt_id", ""))
    speaker_id = str(record.get("speaker_id", ""))
    year = str(record.get("year", ""))

    unified_id = stable_id("spoken_reference", source, file_id, doc_id, utt_id, text)

    return {
        "id": unified_id,
        "source": source,
        "year": year,
        "doc_id": doc_id,
        "utt_id": utt_id,
        "speaker_id": speaker_id,
        "text": text,
        "original_text": original_text,
        "topic": str(record.get("topic", "")),
        "category": str(record.get("category", "")),
        "relation": str(record.get("relation", "")),
        "time": str(record.get("time", "")),
        "style": "spoken",
        "metadata": {
            "file_id": file_id,
            "raw_file": str(record.get("raw_file", "")),
            "purpose": "spoken_style_reference",
        },
    }


def dedupe_key(text: str) -> str:
    lowered = text.lower()
    lowered = SPACE_RE.sub(" ", lowered).strip()
    lowered = re.sub(r"[!?.~,]+", "", lowered)
    return lowered


def collect_spoken_records(
    raw_dir: Path,
    output_path: Path,
    stats_path: Path,
    min_len: int,
    max_len: int,
) -> dict:
    ensure_dir(output_path.parent)

    json_files = sorted(raw_dir.rglob("*.json"))
    csv_files = sorted(raw_dir.rglob("*.csv"))

    stats = {
        "json_files": len(json_files),
        "csv_files": len(csv_files),
        "input_rows": 0,
        "written_rows": 0,
        "deduped_rows": 0,
        "noise_removed_rows": 0,
        "noise_reasons": {},
        "output_path": str(output_path),
    }

    noise_reasons: dict[str, int] = {}
    seen = set()

    with output_path.open("w", encoding="utf-8") as out:
        for path in json_files:
            for raw_record in iter_json_utterances(path):
                stats["input_rows"] += 1
                unified = schema_unify(raw_record)
                is_noise, reason = is_noise_text(
                    unified["text"], unified["original_text"], min_len=min_len, max_len=max_len
                )
                if is_noise:
                    stats["noise_removed_rows"] += 1
                    noise_reasons[reason] = noise_reasons.get(reason, 0) + 1
                    continue

                key = dedupe_key(unified["text"])
                if key in seen:
                    stats["deduped_rows"] += 1
                    continue
                seen.add(key)

                out.write(json.dumps(unified, ensure_ascii=False) + "\n")
                stats["written_rows"] += 1

        for path in csv_files:
            for raw_record in iter_csv_utterances(path):
                stats["input_rows"] += 1
                unified = schema_unify(raw_record)
                is_noise, reason = is_noise_text(
                    unified["text"], unified["original_text"], min_len=min_len, max_len=max_len
                )
                if is_noise:
                    stats["noise_removed_rows"] += 1
                    noise_reasons[reason] = noise_reasons.get(reason, 0) + 1
                    continue

                key = dedupe_key(unified["text"])
                if key in seen:
                    stats["deduped_rows"] += 1
                    continue
                seen.add(key)

                out.write(json.dumps(unified, ensure_ascii=False) + "\n")
                stats["written_rows"] += 1

    stats["noise_reasons"] = dict(sorted(noise_reasons.items(), key=lambda item: item[1], reverse=True))
    stats_path.write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="raw_data에서 구어체 참고용 데이터셋 생성")
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--stats", type=Path, default=DEFAULT_STATS_PATH)
    parser.add_argument("--min-len", type=int, default=6)
    parser.add_argument("--max-len", type=int, default=120)
    args = parser.parse_args()

    stats = collect_spoken_records(
        raw_dir=args.raw_dir,
        output_path=args.output,
        stats_path=args.stats,
        min_len=args.min_len,
        max_len=args.max_len,
    )
    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
