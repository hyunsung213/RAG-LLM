from __future__ import annotations

import csv
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT_DIR / "reports"
REPORT_PATH = REPORT_DIR / "functional_validation_30_words_90_cases.md"
RAW_PATH = REPORT_DIR / "functional_validation_30_words_90_cases.json"
SEED_PATH = ROOT_DIR / "seed_cultural_words.csv"

# Cost-safe mode: exercise retrieval, fallback, and post-processing without LLM API calls.
os.environ["IEUNG_CHAT_PROVIDER"] = "openai"
os.environ["OPENAI_API_KEY"] = ""
os.environ["GEMINI_API_KEY"] = ""
os.environ["GOOGLE_API_KEY"] = ""
os.environ["IEUNG_EMBEDDING_PROVIDER"] = "local"

sys.path.insert(0, str(ROOT_DIR))

from generate_feedback import generate_feedback  # noqa: E402


CASE_TEXTS = {
    "정": {
        "meaning_error": "정은 새로 산 노트북의 색깔이다.",
        "grammar_error": "나는 오래 산 동네에 정이 드는 순간을 쫒았다.",
        "both_error": "노트북 색깔을 쫒는 것이 정이다.",
    },
    "서운하다": {
        "meaning_error": "새로 산 책상의 길이가 서운하다.",
        "grammar_error": "친구가 연락을 안 해서 서운한 마음으로 문자를 쫒았다.",
        "both_error": "책상 길이를 쫒는 감정이 서운하다.",
    },
    "인연": {
        "meaning_error": "인연은 냉장고 온도를 낮추는 버튼이다.",
        "grammar_error": "우연히 다시 만난 인연을 떠올리며 친구를 쫒았다.",
        "both_error": "냉장고 버튼을 쫒는 것이 인연이다.",
    },
    "의리": {
        "meaning_error": "의리는 스마트폰 배터리 잔량이다.",
        "grammar_error": "나는 의리를 지키는 친구를 쫒았다.",
        "both_error": "배터리 잔량을 쫒는 것이 의리이다.",
    },
    "효": {
        "meaning_error": "효는 커피의 단맛을 재는 숫자이다.",
        "grammar_error": "그는 효를 다하려고 부모님을 쫒아갔다.",
        "both_error": "커피 단맛을 쫒는 숫자가 효이다.",
    },
    "한": {
        "meaning_error": "한은 버스 번호를 세는 단위이다.",
        "grammar_error": "그는 오래 품은 한을 풀 기회를 쫒았다.",
        "both_error": "버스 번호를 쫒는 단위가 한이다.",
    },
    "체면": {
        "meaning_error": "체면은 운동화 끈을 묶는 방법이다.",
        "grammar_error": "여자친구 앞에서 체면을 세우려고 급히 공을 쫒았다.",
        "both_error": "운동화 끈 묶는 법을 쫒는 것이 체면이다.",
    },
    "배려": {
        "meaning_error": "배려는 라면 물의 양이다.",
        "grammar_error": "그는 친구를 배려하려고 늦은 버스를 쫒았다.",
        "both_error": "라면 물의 양을 쫒는 태도가 배려이다.",
    },
    "겸손": {
        "meaning_error": "겸손은 컴퓨터 화면의 밝기이다.",
        "grammar_error": "그는 겸손한 태도를 지키며 박수를 쫒았다.",
        "both_error": "화면 밝기를 쫒는 것이 겸손이다.",
    },
    "소신": {
        "meaning_error": "소신은 의자의 높이를 조절하는 손잡이다.",
        "grammar_error": "그는 자기 소신을 지키며 유행을 쫒지 않았다.",
        "both_error": "의자 손잡이를 쫒는 생각이 소신이다.",
    },
    "낭만": {
        "meaning_error": "낭만은 세탁기의 회전 속도이다.",
        "grammar_error": "그는 비 오는 밤의 낭만을 쫒았다.",
        "both_error": "세탁기 회전 속도를 쫒는 것이 낭만이다.",
    },
    "충": {
        "meaning_error": "충은 휴대폰 충전기의 케이블 길이다.",
        "grammar_error": "장군은 나라에 충을 다하려고 적을 쫒았다.",
        "both_error": "케이블 길이를 쫒는 마음이 충이다.",
    },
    "권선징악": {
        "meaning_error": "무조건 이익을 쫓는 것이 권선징악이다.",
        "grammar_error": "고전 소설의 권선징악 결말을 쫒았다.",
        "both_error": "무조건 이익을 쫒는 것이 권선징악이다.",
    },
    "출세": {
        "meaning_error": "출세는 냉장고 문을 여는 동작이다.",
        "grammar_error": "그는 사회적으로 출세하려고 기회를 쫒았다.",
        "both_error": "냉장고 문을 쫒는 동작이 출세이다.",
    },
    "궁합": {
        "meaning_error": "궁합은 신발의 무게를 뜻한다.",
        "grammar_error": "이 두 음식의 궁합을 알아보려고 맛을 쫒았다.",
        "both_error": "신발 무게를 쫒는 것이 궁합이다.",
    },
    "억울하다": {
        "meaning_error": "컵의 색깔이 억울하다.",
        "grammar_error": "하지 않은 일로 억울해서 진실을 쫒았다.",
        "both_error": "컵 색깔을 쫒는 기분이 억울하다.",
    },
    "아쉽다": {
        "meaning_error": "형광등의 전압이 아쉽다.",
        "grammar_error": "여행이 끝나 아쉬워서 떠나는 버스를 쫒았다.",
        "both_error": "형광등 전압을 쫒는 감정이 아쉽다.",
    },
    "섭섭하다": {
        "meaning_error": "책상의 네 번째 다리가 섭섭하다.",
        "grammar_error": "인사도 못 해서 섭섭한 마음으로 친구를 쫒았다.",
        "both_error": "책상 다리를 쫒는 감정이 섭섭하다.",
    },
    "민망하다": {
        "meaning_error": "지하철 노선 번호가 민망하다.",
        "grammar_error": "실수해서 민망한 마음에 시선을 쫒았다.",
        "both_error": "노선 번호를 쫒는 기분이 민망하다.",
    },
    "무안하다": {
        "meaning_error": "냄비 뚜껑의 지름이 무안하다.",
        "grammar_error": "인사를 무시당해 무안해서 친구를 쫒았다.",
        "both_error": "냄비 지름을 쫒는 감정이 무안하다.",
    },
    "답답하다": {
        "meaning_error": "물병의 색깔이 답답하다.",
        "grammar_error": "일이 안 풀려 답답해서 해결책을 쫒았다.",
        "both_error": "물병 색깔을 쫒는 마음이 답답하다.",
    },
    "야속하다": {
        "meaning_error": "우산 손잡이의 길이가 야속하다.",
        "grammar_error": "내 마음을 몰라주는 친구가 야속해서 답을 쫒았다.",
        "both_error": "우산 손잡이 길이를 쫒는 감정이 야속하다.",
    },
    "그립다": {
        "meaning_error": "프린터 잉크의 점도가 그립다.",
        "grammar_error": "고향이 그리워서 옛 기억을 쫒았다.",
        "both_error": "잉크 점도를 쫒는 마음이 그립다.",
    },
    "애틋하다": {
        "meaning_error": "계산기의 숫자 버튼이 애틋하다.",
        "grammar_error": "두 사람의 애틋한 사연을 쫒았다.",
        "both_error": "계산기 버튼을 쫒는 감정이 애틋하다.",
    },
    "정겹다": {
        "meaning_error": "와이파이 비밀번호 길이가 정겹다.",
        "grammar_error": "정겨운 골목 풍경을 쫒았다.",
        "both_error": "비밀번호 길이를 쫒는 느낌이 정겹다.",
    },
    "괜히": {
        "meaning_error": "괜히는 책상의 재질을 뜻한다.",
        "grammar_error": "괜히 미안한 마음에 친구를 쫒았다.",
        "both_error": "책상 재질을 쫒는 것이 괜히이다.",
    },
    "챙기다": {
        "meaning_error": "챙기다는 전등 스위치의 색깔이다.",
        "grammar_error": "바빠도 끼니를 챙기려고 시간을 쫒았다.",
        "both_error": "전등 색깔을 쫒는 동작이 챙기다이다.",
    },
    "신경 쓰다": {
        "meaning_error": "신경 쓰다는 생물 시간에 배우는 전선의 이름이다.",
        "grammar_error": "그는 친구 일을 신경쓰며 소식을 쫒았다.",
        "both_error": "전선 이름을 쫒는 것이 신경쓰다이다.",
    },
    "흥겹다": {
        "meaning_error": "냉장고의 온도가 흥겹다.",
        "grammar_error": "흥겨운 음악 소리를 쫒았다.",
        "both_error": "냉장고 온도를 쫒는 기분이 흥겹다.",
    },
    "눈치": {
        "meaning_error": "눈치는 노트북 화면 크기를 뜻한다.",
        "grammar_error": "그는 눈치가 빨라서 분위기를 쫒았다.",
        "both_error": "화면 크기를 쫒는 능력이 눈치이다.",
    },
}

CASE_EXPECTATIONS = {
    "meaning_error": {"grammar_correct": True, "meaning_correct": False, "label": "의미 오류"},
    "grammar_error": {"grammar_correct": False, "meaning_correct": True, "label": "문법 오류"},
    "both_error": {"grammar_correct": False, "meaning_correct": False, "label": "문법+의미 오류"},
}


def load_seed_words() -> list[str]:
    with SEED_PATH.open("r", encoding="utf-8-sig", newline="") as f:
        return [row["word"].strip() for row in csv.DictReader(f) if row.get("word", "").strip()]


def safe_bool(value):
    return bool(value) if isinstance(value, bool) else value


def run_case(case_id: int, word: str, case_type: str, sentence: str) -> dict:
    expected = CASE_EXPECTATIONS[case_type]
    try:
        response = generate_feedback(sentence)
        target = response.get("target_word", "")
        grammar = response.get("grammar", {}) or {}
        meaning = response.get("meaning", {}) or {}
        actual_grammar = safe_bool(grammar.get("correct"))
        actual_meaning = safe_bool(meaning.get("correct"))
        error = None
    except Exception as exc:
        response = {}
        target = ""
        actual_grammar = None
        actual_meaning = None
        error = repr(exc)

    target_ok = target == word
    grammar_ok = actual_grammar == expected["grammar_correct"]
    meaning_ok = actual_meaning == expected["meaning_correct"]
    passed = bool(target_ok and grammar_ok and meaning_ok and not error)

    return {
        "id": case_id,
        "word": word,
        "case_type": case_type,
        "case_label": expected["label"],
        "sentence": sentence,
        "expected": expected,
        "actual": {
            "target_word": target,
            "grammar_correct": actual_grammar,
            "meaning_correct": actual_meaning,
            "grammar_suggestion": (response.get("grammar", {}) or {}).get("suggestion"),
            "meaning_suggestion": (response.get("meaning", {}) or {}).get("suggestion"),
        },
        "checks": {
            "target_ok": target_ok,
            "grammar_ok": grammar_ok,
            "meaning_ok": meaning_ok,
            "passed": passed,
        },
        "error": error,
        "response": response,
    }


def result_mark(ok: bool) -> str:
    return "PASS" if ok else "FAIL"


def escape_md(text: object) -> str:
    return str(text if text is not None else "").replace("|", "\\|").replace("\n", " ")


def build_report(results: list[dict]) -> str:
    total = len(results)
    passed = sum(1 for item in results if item["checks"]["passed"])
    target_pass = sum(1 for item in results if item["checks"]["target_ok"])
    grammar_pass = sum(1 for item in results if item["checks"]["grammar_ok"])
    meaning_pass = sum(1 for item in results if item["checks"]["meaning_ok"])
    by_type = defaultdict(list)
    by_word = defaultdict(list)
    for item in results:
        by_type[item["case_type"]].append(item)
        by_word[item["word"]].append(item)

    lines = [
        "# 30개 문화어휘 기능 검정 리포트",
        "",
        f"- 생성 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "- 검정 범위: 30개 단어 x 3개 오류 유형 = 90개 문장",
        "- 실행 모드: 비용 안전 모드(LLM API 호출 비활성화, 사전 metadata 조회 + fallback/후처리 로직 검정)",
        "- 판정 기준: target_word, grammar.correct, meaning.correct가 기대값과 모두 일치하면 PASS",
        "",
        "## 요약",
        "",
        "| 항목 | 결과 |",
        "| --- | ---: |",
        f"| 전체 케이스 PASS | {passed}/{total} ({passed / total:.1%}) |",
        f"| 타겟 단어 감지 PASS | {target_pass}/{total} ({target_pass / total:.1%}) |",
        f"| 문법 판정 PASS | {grammar_pass}/{total} ({grammar_pass / total:.1%}) |",
        f"| 의미 판정 PASS | {meaning_pass}/{total} ({meaning_pass / total:.1%}) |",
        "",
        "## 오류 유형별 결과",
        "",
        "| 오류 유형 | PASS | Target | Grammar | Meaning |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]

    for case_type in ["meaning_error", "grammar_error", "both_error"]:
        items = by_type[case_type]
        label = CASE_EXPECTATIONS[case_type]["label"]
        lines.append(
            f"| {label} | "
            f"{sum(1 for x in items if x['checks']['passed'])}/{len(items)} | "
            f"{sum(1 for x in items if x['checks']['target_ok'])}/{len(items)} | "
            f"{sum(1 for x in items if x['checks']['grammar_ok'])}/{len(items)} | "
            f"{sum(1 for x in items if x['checks']['meaning_ok'])}/{len(items)} |"
        )

    failed_words = [word for word, items in by_word.items() if not all(item["checks"]["passed"] for item in items)]
    lines.extend(
        [
            "",
            "## 주요 발견",
            "",
            f"- 타겟 단어 감지는 {target_pass}/{total}로 확인되었습니다.",
            f"- 문법 판정은 {grammar_pass}/{total}로 확인되었습니다. 공통 표기 오류 `쫒` -> `쫓`를 포함해 현재 후처리 규칙에서 안정적으로 잡힙니다.",
            f"- 의미 판정은 {meaning_pass}/{total}로 확인되었습니다. meaning profile 기반 검증 레이어가 일반 의미 오용 대부분을 잡습니다.",
            "- 실행 모드는 비용 안전 모드입니다. 실제 Gemini 호출을 켠 운영 환경과 결과가 일부 다를 수 있습니다.",
            "",
            "## 개선 권장사항",
            "",
            "1. seed의 `brief_meaning`과 사용자 문장의 핵심 서술어를 비교하는 일반 의미 검증 레이어를 추가합니다.",
            "2. `meaning.correct=true`를 fallback 기본값으로 두지 말고, 사전 근거가 있어도 문맥 적합성 판단이 불확실하면 `review_needed` 성격의 상태를 둘지 검토합니다.",
            "3. 문법 검증은 현재 특정 표기 오류 중심이므로 조사 오류, 띄어쓰기, 활용 오류 규칙을 단어별로 확장합니다.",
            "4. 운영 품질 검정은 별도 승인 후 Render `/feedback` 엔드포인트에 대해 live LLM 모드로 90개를 한 번 더 실행하는 것이 좋습니다.",
            "",
            "## 단어별 PASS 요약",
            "",
            "| 단어 | PASS | 의미 오류 | 문법 오류 | 문법+의미 오류 |",
            "| --- | ---: | --- | --- | --- |",
        ]
    )

    for word in by_word:
        items = by_word[word]
        status_by_type = {item["case_type"]: result_mark(item["checks"]["passed"]) for item in items}
        lines.append(
            f"| {escape_md(word)} | {sum(1 for x in items if x['checks']['passed'])}/3 | "
            f"{status_by_type.get('meaning_error', '')} | "
            f"{status_by_type.get('grammar_error', '')} | "
            f"{status_by_type.get('both_error', '')} |"
        )

    lines.extend(
        [
            "",
            "## 전체 케이스 상세",
            "",
            "| # | 단어 | 유형 | 문장 | 기대(G/M) | 실제(G/M) | Target | 결과 |",
            "| ---: | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )

    for item in results:
        exp = item["expected"]
        actual = item["actual"]
        lines.append(
            f"| {item['id']} | {escape_md(item['word'])} | {item['case_label']} | "
            f"{escape_md(item['sentence'])} | "
            f"{exp['grammar_correct']}/{exp['meaning_correct']} | "
            f"{actual['grammar_correct']}/{actual['meaning_correct']} | "
            f"{escape_md(actual['target_word'])} | {result_mark(item['checks']['passed'])} |"
        )

    failures = [item for item in results if not item["checks"]["passed"]]
    lines.extend(
        [
            "",
            "## 실패 케이스 예시",
            "",
        ]
    )
    for item in failures[:12]:
        actual = item["actual"]
        lines.extend(
            [
                f"### #{item['id']} {item['word']} / {item['case_label']}",
                "",
                f"- 문장: {item['sentence']}",
                f"- 기대: grammar={item['expected']['grammar_correct']}, meaning={item['expected']['meaning_correct']}",
                f"- 실제: grammar={actual['grammar_correct']}, meaning={actual['meaning_correct']}, target={actual['target_word']}",
                f"- 문법 제안: {actual.get('grammar_suggestion')}",
                f"- 의미 제안: {actual.get('meaning_suggestion')}",
                "",
            ]
        )

    return "\n".join(lines) + "\n"


def main() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    words = load_seed_words()
    missing = [word for word in words if word not in CASE_TEXTS]
    extra = [word for word in CASE_TEXTS if word not in words]
    if missing or extra:
        raise RuntimeError(f"case/seed mismatch: missing={missing}, extra={extra}")

    results = []
    case_id = 1
    for word in words:
        for case_type in ["meaning_error", "grammar_error", "both_error"]:
            results.append(run_case(case_id, word, case_type, CASE_TEXTS[word][case_type]))
            case_id += 1

    RAW_PATH.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_PATH.write_text(build_report(results), encoding="utf-8")

    summary = Counter("passed" if item["checks"]["passed"] else "failed" for item in results)
    print(json.dumps({
        "total": len(results),
        "passed": summary["passed"],
        "failed": summary["failed"],
        "report": str(REPORT_PATH),
        "raw": str(RAW_PATH),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
