from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_INPUT_PATH = ROOT_DIR / "output" / "normalized" / "rag_documents.jsonl"
VALIDATION_DIR = ROOT_DIR / "output" / "validation"

REPORT_PATH = VALIDATION_DIR / "rag_validation_report.md"
SUMMARY_PATH = VALIDATION_DIR / "rag_validation_summary.json"
ACCEPTED_PATH = VALIDATION_DIR / "rag_documents_accepted.jsonl"
REJECTED_PATH = VALIDATION_DIR / "rag_documents_rejected.jsonl"
REVIEW_NEEDED_PATH = VALIDATION_DIR / "rag_documents_review_needed.jsonl"


ALLOWED_POS = {"명사", "동사", "형용사", "부사", "동사구", "명사구"}
REJECT_POS = {"접사", "의존 명사", "품사 없음", "관형사", "대명사", ""}
STRICT_ONE_CHAR_WORDS = {"정", "한", "효", "충"}

API_ERROR_PATTERNS = [
    "Unregistered key",
    "error_code",
    "error message",
    "insufficient_quota",
    "RateLimitError",
]

GENERAL_FORBIDDEN_BY_WORD = {
    "정": ["쇠", "연장", "알약", "단위", "접두사", "접미사", "바른 일", "바른길"],
    "한": ["하나", "같은", "대략", "끝", "조건", "접두사", "접미사", "한글", "한가"],
    "효": ["효과", "효율", "효과음"],
    "충": ["충격", "충고", "충돌", "충분"],
}

TARGET_KEYWORDS_BY_WORD = {
    "정": ["마음", "사랑", "가깝", "친근", "애착"],
    "한": ["원망", "억울", "슬퍼", "슬픔", "응어리"],
    "효": ["부모", "모시", "받드", "효도"],
    "충": ["임금", "나라", "충성", "공동체"],
    "소신": ["굳게", "믿는 생각", "생각", "원칙", "의견"],
}

REVIEW_RELATED_WORDS = {
    "눈치": {"눈치 보다", "눈치를 보다", "눈치채다", "눈치껏"},
    "배려": {"배려하다", "배려심"},
    "겸손": {"겸손하다", "겸손히"},
    "출세": {"출세하다", "출세욕", "입신출세"},
    "낭만": {"낭만적", "낭만주의"},
    "인연": {"인연하다"},
    "효": {"효도", "효도하다"},
}

OBVIOUS_NOISE_DEFINITION_PATTERNS = {
    "눈치": ["정어리", "송사리"],
    "궁합": ["후궁", "궁중", "내전"],
    "배려": ["배반되고", "어그러짐"],
    "소신": ["음력", "물때", "작은 신뢰와 의리", "불사름", "다 타 버림", "소갈", "오줌"],
    "인연": ["연기라는 뜻", "잡아당겨 늘임", "덩굴이 줄을 타고", "나무뿌리나 바위", "권세 있는 연줄", "인(因)과 연(緣)", "대중가요", "관자뼈"],
    "의리": ["김천시", "아포읍", "면적은"],
    "출세": ["세금을 냄", "숨어 살던 사람이 세상에 나옴", "세상에 태어남", "불보살", "성자", "수행 생활"],
    "체면": ["직위를 교체하여"],
    "챙기다": ["잠기다", "가리다"],
}


def ensure_output_dir() -> None:
    VALIDATION_DIR.mkdir(parents=True, exist_ok=True)


def reset_outputs() -> None:
    ensure_output_dir()
    for path in [REPORT_PATH, SUMMARY_PATH, ACCEPTED_PATH, REJECTED_PATH, REVIEW_NEEDED_PATH]:
        path.write_text("", encoding="utf-8")


def append_jsonl(path: Path, data: dict) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(data, ensure_ascii=False) + "\n")


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value).strip()


def normalize_word(value: str) -> str:
    """사전 표기의 하이픈/공백은 비교용으로만 제거한다."""
    return re.sub(r"[\s\-\^·ㆍ_]+", "", value or "")


def contains_any(text: str, patterns: list[str]) -> list[str]:
    return [pattern for pattern in patterns if pattern and pattern in text]


def extract_doc_fields(doc: dict) -> dict:
    metadata = doc.get("metadata") if isinstance(doc.get("metadata"), dict) else {}
    return {
        "doc_type": clean_text(doc.get("doc_type")),
        "word": clean_text(doc.get("word")),
        "content": clean_text(doc.get("content")),
        "source_word": clean_text(metadata.get("source_word") or doc.get("word")),
        "pos": clean_text(metadata.get("pos")),
        "metadata": metadata,
    }


def validate_special_word(word: str, source_word: str, pos: str, content: str) -> tuple[str | None, list[str], list[str]]:
    """단어별 문화어휘 목표 의미가 뚜렷한 경우 우선 규칙을 적용한다."""
    reasons: list[str] = []
    warnings: list[str] = []
    source_norm = normalize_word(source_word)

    forbidden = contains_any(source_word + "\n" + content, GENERAL_FORBIDDEN_BY_WORD.get(word, []))
    if forbidden:
        reasons.append(f"{word} 관련 금지 패턴 포함: {', '.join(forbidden)}")
        return "rejected", reasons, warnings

    if word == "정":
        if pos != "명사":
            reasons.append("정의 문화어휘 목표 의미는 명사만 허용")
            return "rejected", reasons, warnings
        if source_word == "정" and contains_any(content, TARGET_KEYWORDS_BY_WORD["정"]):
            reasons.append("정의 목표 의미(관계/감정/친근한 마음)와 관련 있음")
            return "accepted", reasons, warnings
        if source_norm != "정":
            warnings.append("한 글자 seed word에서 파생어 노이즈 가능성 높음")
            reasons.append("정 문서인데 source_word가 정확히 일치하지 않음")
            return "rejected", reasons, warnings
        reasons.append("정의 문화어휘 의미와 관련성을 자동 확정하기 어려움")
        return "review_needed", reasons, warnings

    if word == "한":
        if pos in {"관형사", "접사"}:
            reasons.append("한의 목표 의미는 명사이므로 관형사/접사는 제외")
            return "rejected", reasons, warnings
        if source_word == "한" and contains_any(content, TARGET_KEYWORDS_BY_WORD["한"]):
            reasons.append("한의 목표 의미(억울함/슬픔/응어리진 마음)와 관련 있음")
            return "accepted", reasons, warnings
        if source_norm != "한":
            warnings.append("한 글자 seed word에서 파생어 노이즈 가능성 높음")
            reasons.append("한 문서인데 source_word가 정확히 일치하지 않음")
            return "rejected", reasons, warnings
        reasons.append("한의 문화어휘 의미와 관련성을 자동 확정하기 어려움")
        return "review_needed", reasons, warnings

    if word == "효":
        if source_word in REVIEW_RELATED_WORDS["효"]:
            reasons.append("효 관련 확장 표현 후보")
            return "review_needed", reasons, warnings
        if source_word == "효" and contains_any(content, TARGET_KEYWORDS_BY_WORD["효"]):
            reasons.append("효의 목표 의미(부모를 잘 모심)와 관련 있음")
            return "accepted", reasons, warnings
        if source_norm != "효":
            warnings.append("한 글자 seed word에서 파생어 노이즈 가능성 높음")
            reasons.append("효 문서인데 source_word가 정확히 일치하지 않음")
            return "rejected", reasons, warnings
        reasons.append("효의 문화어휘 의미와 관련성을 자동 확정하기 어려움")
        return "review_needed", reasons, warnings

    if word == "충":
        if source_word == "충" and contains_any(content, TARGET_KEYWORDS_BY_WORD["충"]):
            reasons.append("충의 목표 의미(나라/임금/충성)와 관련 있음")
            return "accepted", reasons, warnings
        if source_norm != "충":
            warnings.append("한 글자 seed word에서 파생어 노이즈 가능성 높음")
            reasons.append("충 문서인데 source_word가 정확히 일치하지 않음")
            return "rejected", reasons, warnings
        reasons.append("충의 문화어휘 의미와 관련성을 자동 확정하기 어려움")
        return "review_needed", reasons, warnings

    if word == "소신":
        if source_word == "소신" and all(token in content for token in ["신하", "임금"]) and "낮추" in content:
            reasons.append("소신의 대명사 의미(옛날 신하가 자기를 낮추어 이르던 말)는 제외")
            return "rejected", reasons, warnings
        if source_word == "소신" and contains_any(content, TARGET_KEYWORDS_BY_WORD["소신"]):
            reasons.append("소신의 목표 의미(굳게 믿는 생각/원칙)와 관련 있음")
            return "accepted", reasons, warnings

    return None, reasons, warnings


def validate_document(doc: dict) -> dict:
    fields = extract_doc_fields(doc)
    doc_type = fields["doc_type"]
    word = fields["word"]
    content = fields["content"]
    source_word = fields["source_word"]
    pos = fields["pos"]

    reasons: list[str] = []
    warnings: list[str] = []
    score = 0.5

    # 기본 reject 조건: 문서 자체가 검색/임베딩에 부적합한 경우
    if not word or not content:
        reasons.append("content 또는 word가 비어 있음")
        return build_validation("rejected", 0.0, reasons, warnings)

    api_errors = contains_any(content, API_ERROR_PATTERNS)
    if api_errors:
        reasons.append(f"API 오류 응답 포함: {', '.join(api_errors)}")
        return build_validation("rejected", 0.02, reasons, warnings)

    if doc_type != "word_definition":
        reasons.append("doc_type이 word_definition이 아님")
        return build_validation("rejected", 0.05, reasons, warnings)
    reasons.append("doc_type이 word_definition임")
    score += 0.08

    if not source_word:
        reasons.append("metadata.source_word가 비어 있음")
        return build_validation("rejected", 0.08, reasons, warnings)

    obvious_noise = contains_any(content, OBVIOUS_NOISE_DEFINITION_PATTERNS.get(word, []))
    if obvious_noise:
        reasons.append(f"문화어휘 목표 의미와 무관한 명백한 노이즈 정의 포함: {', '.join(obvious_noise)}")
        return build_validation("rejected", 0.05, reasons, warnings)

    if pos in REJECT_POS:
        reasons.append(f"품사가 reject 목록에 포함됨: {pos or '품사 없음'}")
        return build_validation("rejected", 0.12, reasons, warnings)
    if pos in ALLOWED_POS:
        reasons.append("품사가 허용 목록에 포함됨")
        score += 0.12
    else:
        warnings.append(f"허용 목록에 없는 품사: {pos or '품사 없음'}")
        score -= 0.08

    special_status, special_reasons, special_warnings = validate_special_word(word, source_word, pos, content)
    reasons.extend(special_reasons)
    warnings.extend(special_warnings)
    if special_status:
        if special_status == "accepted":
            score += 0.28
        elif special_status == "review_needed":
            score = min(score, 0.62)
        else:
            score = min(score, 0.18)
        return build_validation(special_status, score, reasons, warnings)

    exact_match = source_word == word
    normalized_match = normalize_word(source_word) == normalize_word(word)
    related_review = source_word in REVIEW_RELATED_WORDS.get(word, set())

    if word in STRICT_ONE_CHAR_WORDS and not exact_match and not related_review:
        warnings.append("한 글자 seed word에서 파생어 노이즈 가능성 높음")
        reasons.append("한 글자 단어에서 source_word가 word와 정확히 일치하지 않고 허용 목록에도 없음")
        return build_validation("rejected", 0.15, reasons, warnings)

    if related_review:
        reasons.append("source_word가 허용된 관련 표현 후보에 포함됨")
        return build_validation("review_needed", 0.58, reasons, warnings)

    if exact_match:
        reasons.append("source_word가 seed word와 정확히 일치함")
        score += 0.25
        return build_validation("accepted", score, reasons, warnings)

    if normalized_match:
        reasons.append("source_word가 표기상 하이픈/공백만 다른 후보임")
        return build_validation("review_needed", 0.6, reasons, warnings)

    if normalize_word(word) in normalize_word(source_word):
        reasons.append("source_word가 seed word를 포함하는 파생어 후보임")
        warnings.append("서비스 확장 표현으로 쓸 수 있는지 사람 검수가 필요함")
        return build_validation("review_needed", 0.5, reasons, warnings)

    reasons.append("source_word가 seed word와 불일치함")
    reasons.append("명백히 무관한 파생어 또는 검색 노이즈 가능성")
    return build_validation("rejected", 0.12, reasons, warnings)


def build_validation(status: str, score: float, reasons: list[str], warnings: list[str]) -> dict:
    return {
        "status": status,
        "score": round(max(0.0, min(score, 1.0)), 2),
        "reasons": reasons,
        "warnings": warnings,
    }


def output_path_for_status(status: str) -> Path:
    if status == "accepted":
        return ACCEPTED_PATH
    if status == "review_needed":
        return REVIEW_NEEDED_PATH
    return REJECTED_PATH


def read_and_validate(input_path: Path) -> dict:
    stats = {
        "total": 0,
        "accepted": 0,
        "rejected": 0,
        "review_needed": 0,
        "by_word": defaultdict(lambda: {"total": 0, "accepted": 0, "rejected": 0, "review_needed": 0}),
        "reject_reasons": Counter(),
        "review_reasons": Counter(),
        "examples": {"accepted": [], "rejected": [], "review_needed": []},
    }

    with input_path.open("r", encoding="utf-8-sig") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue

            try:
                doc = json.loads(line)
            except json.JSONDecodeError as exc:
                doc = {
                    "doc_id": f"json_parse_error_line_{line_no}",
                    "doc_type": "invalid_json",
                    "word": "",
                    "content": line[:500],
                    "metadata": {},
                    "validation": build_validation("rejected", 0.0, [f"JSON parse error: {exc}"], []),
                }
                write_validated_doc(doc, stats)
                continue

            doc["validation"] = validate_document(doc)
            write_validated_doc(doc, stats)

    return stats


def write_validated_doc(doc: dict, stats: dict) -> None:
    validation = doc.get("validation", {})
    status = validation.get("status", "rejected")
    word = clean_text(doc.get("word")) or "__unknown__"

    append_jsonl(output_path_for_status(status), doc)

    stats["total"] += 1
    stats[status] += 1
    stats["by_word"][word]["total"] += 1
    stats["by_word"][word][status] += 1

    if status == "rejected":
        stats["reject_reasons"].update(actionable_reasons(validation.get("reasons", [])))
    elif status == "review_needed":
        stats["review_reasons"].update(actionable_reasons(validation.get("reasons", [])))

    if len(stats["examples"][status]) < 10:
        stats["examples"][status].append(compact_example(doc))


def compact_example(doc: dict) -> dict:
    metadata = doc.get("metadata") if isinstance(doc.get("metadata"), dict) else {}
    return {
        "doc_id": doc.get("doc_id"),
        "word": doc.get("word"),
        "source_word": metadata.get("source_word"),
        "pos": metadata.get("pos"),
        "source": metadata.get("source"),
        "content": clean_text(doc.get("content"))[:180],
        "validation": doc.get("validation"),
    }


def actionable_reasons(reasons: list[str]) -> list[str]:
    """리포트 TOP 사유에는 공통 통과 사유보다 실제 조치가 필요한 사유를 우선 집계한다."""
    ignored = {
        "doc_type이 word_definition임",
        "품사가 허용 목록에 포함됨",
        "source_word가 seed word와 정확히 일치함",
    }
    filtered = [reason for reason in reasons if reason not in ignored]
    return filtered or reasons


def make_summary(stats: dict) -> dict:
    by_word = {word: dict(counts) for word, counts in sorted(stats["by_word"].items())}
    noisy_words = find_noisy_words(by_word)
    return {
        "total": stats["total"],
        "accepted": stats["accepted"],
        "rejected": stats["rejected"],
        "review_needed": stats["review_needed"],
        "by_word": by_word,
        "top_reject_reasons": stats["reject_reasons"].most_common(20),
        "top_review_reasons": stats["review_reasons"].most_common(20),
        "noisy_words": noisy_words,
    }


def find_noisy_words(by_word: dict) -> list[dict]:
    noisy = []
    for word, counts in by_word.items():
        total = counts.get("total", 0)
        if total == 0:
            continue
        rejected = counts.get("rejected", 0)
        review = counts.get("review_needed", 0)
        noise_ratio = (rejected + review) / total
        if total >= 5 and noise_ratio >= 0.5:
            noisy.append(
                {
                    "word": word,
                    "total": total,
                    "rejected": rejected,
                    "review_needed": review,
                    "noise_ratio": round(noise_ratio, 3),
                }
            )
    return sorted(noisy, key=lambda item: (-item["noise_ratio"], -item["total"], item["word"]))


def percent(part: int, total: int) -> str:
    if total == 0:
        return "0.0%"
    return f"{part / total * 100:.1f}%"


def write_summary_and_report(stats: dict) -> dict:
    summary = make_summary(stats)
    SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_PATH.write_text(build_report(summary, stats["examples"]), encoding="utf-8")
    return summary


def build_report(summary: dict, examples: dict) -> str:
    total = summary["total"]
    lines = [
        "# RAG Document Validation Report",
        "",
        "## Summary",
        "",
        f"- 전체 문서 수: {total}",
        f"- accepted: {summary['accepted']} ({percent(summary['accepted'], total)})",
        f"- rejected: {summary['rejected']} ({percent(summary['rejected'], total)})",
        f"- review_needed: {summary['review_needed']} ({percent(summary['review_needed'], total)})",
        "",
        "## Word Counts",
        "",
        "| word | total | accepted | rejected | review_needed |",
        "|---|---:|---:|---:|---:|",
    ]

    for word, counts in summary["by_word"].items():
        lines.append(
            f"| {word} | {counts['total']} | {counts['accepted']} | {counts['rejected']} | {counts['review_needed']} |"
        )

    lines.extend(
        [
            "",
            "## Top Reject Reasons",
            "",
            *format_reason_list(summary["top_reject_reasons"]),
            "",
            "## Top Review Needed Reasons",
            "",
            *format_reason_list(summary["top_review_reasons"]),
            "",
            "## Noisy Words",
            "",
        ]
    )

    if summary["noisy_words"]:
        for item in summary["noisy_words"]:
            lines.append(
                f"- {item['word']}: total={item['total']}, rejected={item['rejected']}, "
                f"review_needed={item['review_needed']}, noise_ratio={item['noise_ratio']}"
            )
    else:
        lines.append("- 노이즈가 많은 단어가 자동 기준에 걸리지 않았습니다.")

    for status in ["accepted", "rejected", "review_needed"]:
        lines.extend(["", f"## {status} Examples", ""])
        lines.extend(format_examples(examples.get(status, [])))

    lines.extend(
        [
            "",
            "## Next Actions",
            "",
            "- ChromaDB에는 우선 `rag_documents_accepted.jsonl`만 넣는 것을 권장합니다.",
            "- `review_needed`는 사람이 검수한 뒤 accepted/rejected로 다시 병합하세요.",
            "- `rejected`는 임베딩 대상에서 제외하세요.",
            "- 한 글자 단어인 정/한/효/충은 엄격 필터링을 유지하세요.",
        ]
    )
    return "\n".join(lines) + "\n"


def format_reason_list(items: list) -> list[str]:
    if not items:
        return ["- 없음"]
    return [f"- {reason}: {count}" for reason, count in items]


def format_examples(items: list[dict]) -> list[str]:
    if not items:
        return ["- 없음"]
    lines = []
    for item in items:
        validation = item.get("validation", {})
        reason = "; ".join(validation.get("reasons", [])[:3])
        lines.append(
            f"- `{item.get('doc_id')}` / word=`{item.get('word')}` / "
            f"source_word=`{item.get('source_word')}` / pos=`{item.get('pos')}` / reason={reason}"
        )
    return lines


def main() -> None:
    parser = argparse.ArgumentParser(description="RAG 문서 품질 검증")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT_PATH)
    args = parser.parse_args()

    reset_outputs()
    stats = read_and_validate(args.input)
    summary = write_summary_and_report(stats)

    print(json.dumps(
        {
            "total": summary["total"],
            "accepted": summary["accepted"],
            "rejected": summary["rejected"],
            "review_needed": summary["review_needed"],
            "report": str(REPORT_PATH),
            "summary": str(SUMMARY_PATH),
        },
        ensure_ascii=False,
        indent=2,
    ))


if __name__ == "__main__":
    main()
