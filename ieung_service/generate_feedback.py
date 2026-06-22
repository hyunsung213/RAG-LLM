from __future__ import annotations

import json
import os
import re
import sys
import csv
import json
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT_DIR / "dictionary_pipeline" / "retrieval"))
sys.path.insert(0, str(ROOT_DIR / "spoken_labeling"))

try:
    from embedding_utils import is_quota_error
except Exception:
    def is_quota_error(_exc) -> bool:
        return False


try:
    from search_dictionary_rag import extract_target_word, search_dictionary_documents_balanced
except Exception:
    def load_culture_words() -> list[str]:
        seed_path = ROOT_DIR / "seed_cultural_words.csv"
        if not seed_path.exists():
            return []
        with seed_path.open("r", encoding="utf-8-sig", newline="") as f:
            rows = list(csv.DictReader(f))
        return [str(row.get("word", "")).strip() for row in rows if str(row.get("word", "")).strip()]

    def load_related_patterns() -> dict[str, list[str]]:
        config_path = ROOT_DIR / "spoken_search_config.json"
        if not config_path.exists():
            return {}
        with config_path.open("r", encoding="utf-8-sig") as f:
            data = json.load(f)
        return {
            str(word).strip(): [str(pattern).strip() for pattern in patterns if str(pattern).strip()]
            for word, patterns in (data.get("related_patterns", {}) or {}).items()
        }

    def normalize_match_text(text: str) -> str:
        return re.sub(r"[\s\-\^·ㆍ_]+", "", text or "")

    CULTURE_WORDS = load_culture_words()
    RELATED_PATTERNS = load_related_patterns()

    def extract_target_word(sentence: str) -> str | None:
        normalized_sentence = normalize_match_text(sentence)
        for word in sorted(CULTURE_WORDS, key=len, reverse=True):
            normalized_word = normalize_match_text(word)
            if word in sentence or normalized_word in normalized_sentence:
                return word
            for pattern in RELATED_PATTERNS.get(word, []):
                normalized_pattern = normalize_match_text(pattern)
                if pattern in sentence or (normalized_pattern and normalized_pattern in normalized_sentence):
                    return word
        return None

    def search_dictionary_documents_balanced(_query: str, top_k: int = 6) -> list[dict]:
        return []


from search_spoken_examples import search_spoken_examples


DEFAULT_SENTENCE = "나는 이 카페를 정이 들었다."
TPO_CONFIG_PATH = ROOT_DIR / "tpo_config.json"


SYSTEM_PROMPT = """너는 외국인 한국어 학습자를 위한 AI 기반 한국어 표현 튜터다.

문장을 문법, 의미, TPO 기준으로 짧게 분석한다.
문법/의미 판단은 한국어기초사전과 우리말샘을 우선 사용한다.
구어체 예문은 말투 참고용으로만 사용한다.
target_word는 다른 단어로 바꾸지 않는다.
반드시 JSON 객체만 출력한다.
reason에는 반드시 출처를 포함한다. 예: [한국어기초사전] ..., [우리말샘] ..., [모두의 말뭉치] ...
"""


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def load_settings() -> dict:
    load_dotenv(ROOT_DIR / ".env")

    chat_provider = os.getenv("IEUNG_CHAT_PROVIDER", "openai").strip().lower()
    openai_api_key = os.getenv("OPENAI_API_KEY")
    gemini_api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

    return {
        "chat_provider": chat_provider,
        "openai_api_key": openai_api_key,
        "gemini_api_key": gemini_api_key,
        "chat_model": os.getenv("OPENAI_CHAT_MODEL", "gpt-4.1-mini"),
        "gemini_chat_model": os.getenv("GEMINI_CHAT_MODEL", "gemini-2.5-flash"),
    }


def clean_one_line(text: str, max_len: int = 220) -> str:
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    if len(text) > max_len:
        return text[:max_len].rstrip() + "..."
    return text


def classify_dictionary_source(doc: dict) -> str:
    source = str(doc.get("source", "")).lower()
    if source == "krdict":
        return "한국어기초사전"
    if source == "opendict":
        return "우리말샘"
    return "기타 사전"


def build_dictionary_evidence_summary(docs: list[dict]) -> dict:
    grouped = {"한국어기초사전": [], "우리말샘": [], "기타 사전": []}
    for doc in docs:
        label = classify_dictionary_source(doc)
        content = clean_one_line(doc.get("content", ""))
        if content and content not in grouped[label]:
            grouped[label].append(content)
    return grouped


def build_dictionary_evidence_block(docs: list[dict]) -> str:
    if not docs:
        return "검색된 사전 근거가 없습니다."

    blocks = []
    for index, doc in enumerate(docs[:2], start=1):
        blocks.append(
            "\n".join(
                [
                    f"[사전 근거 {index}]",
                    f"source: {doc.get('source', '')}",
                    f"word: {doc.get('word', '')}",
                    f"content: {clean_one_line(doc.get('content', ''), max_len=300)}",
                ]
            )
        )
    return "\n\n".join(blocks)


def build_spoken_evidence_block(result: dict) -> str:
    examples = result.get("examples", [])
    if not examples:
        return "검색된 구어체 참고 예문이 없습니다."

    blocks = []
    for index, example in enumerate(examples[:2], start=1):
        blocks.append(
            "\n".join(
                [
                    f"[구어체 예문 {index}]",
                    f"text: {example.get('text', '')}",
                    f"source: {example.get('source', '')}",
                ]
            )
        )
    return "\n\n".join(blocks)


def build_tpo_block() -> str:
    tpo_config = load_json(TPO_CONFIG_PATH)
    lines = []
    for key in ["공적", "사적", "반격식"]:
        item = tpo_config.get(key, {})
        lines.append(f"{key}: {item.get('principle', '')}")
    return "\n".join(lines)


def build_user_prompt(user_sentence: str, dictionary_docs: list[dict], spoken_result: dict, target_word: str | None) -> str:
    return f"""[사용자 문장]
{user_sentence}

[대상 문화어휘]
{target_word or ""}

[사전 근거]
{build_dictionary_evidence_block(dictionary_docs)}

[구어체 참고 예문]
{build_spoken_evidence_block(spoken_result)}

[TPO 분류 기준]
{build_tpo_block()}

[지시]
1. 문법 판단
2. 의미 판단
3. TPO별 추천 문장 3개 작성
4. reason은 출처 포함 1~2문장으로 짧게 작성
5. TPO 추천은 원문과 같은 사건, 대상, 관계, 장소를 유지하고 말투와 격식만 바꾼다.
6. 원문에 없는 상황을 만들지 마라. 예: "공식적인 자리", "중요한 미팅" 같은 새 배경 추가 금지.
7. 공적 표현이 어색한 사적 사건이어도 같은 내용을 더 격식 있게만 바꾼다.

[출력 JSON 형식]
{{
  "original_sentence": "{user_sentence}",
  "target_word": "{target_word or ''}",
  "grammar": {{
    "correct": true,
    "reason": "[한국어기초사전] ... [우리말샘] ...",
    "suggestion": null
  }},
  "meaning": {{
    "correct": true,
    "reason": "[한국어기초사전] ... [우리말샘] ...",
    "suggestion": null
  }},
  "tpo": {{
    "best_fit": "공적 | 사적 | 반격식",
    "reason": "[모두의 말뭉치] ...",
    "공적": "...",
    "사적": "...",
    "반격식": "..."
  }},
  "summary": "..."
}}

불필요한 키는 추가하지 마라."""


def join_reason_parts(parts: list[str]) -> str:
    cleaned = [part.strip() for part in parts if str(part or "").strip()]
    return " ".join(cleaned)


def build_dictionary_reason(summary: dict, fallback_message: str) -> str:
    parts = []
    if summary.get("한국어기초사전"):
        parts.append(f"[한국어기초사전] {summary['한국어기초사전'][0]}")
    if summary.get("우리말샘"):
        parts.append(f"[우리말샘] {summary['우리말샘'][0]}")
    if parts:
        parts.append(f"[판단] {fallback_message}")
    else:
        parts.append(f"[사전 근거 없음] {fallback_message}")
    return join_reason_parts(parts)


def build_spoken_reason(spoken_examples: list[dict]) -> str:
    if not spoken_examples:
        return "[모두의 말뭉치] 구어체 참고 예문이 없어 기본 말투 규칙으로 추천했습니다."

    parts = []
    for example in spoken_examples[:2]:
        parts.append(f"[모두의 말뭉치] {clean_one_line(example.get('text', ''), max_len=60)}")
    return join_reason_parts(parts)


def parse_model_json(raw_text: str) -> dict:
    text = (raw_text or "").strip()
    if not text:
        return {"json_parse_error": True, "raw_text": raw_text}
    if text.startswith("```"):
        text = re.sub(r"^```json\s*", "", text)
        text = re.sub(r"^```\s*", "", text)
        text = re.sub(r"\s*```$", "", text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and start < end:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                pass
    return {"json_parse_error": True, "raw_text": raw_text}


PARTICLE_RE = re.compile(r"(은|는|이|가|을|를|에|에서|으로|로|와|과|랑|하고|도|만|까지|부터|보다)$")
GENERIC_CONTEXT_WORDS = {
    "문장",
    "표현",
    "사람",
    "상황",
    "정도",
    "때문",
    "이번",
    "오늘",
    "내일",
    "어제",
}


def normalize_context_text(text: str) -> str:
    return re.sub(r"[\s\-\^·ㆍ_.,!?\"'()]+", "", text or "")


def strip_particle(token: str) -> str:
    previous = token
    while True:
        current = PARTICLE_RE.sub("", previous)
        if current == previous:
            return current
        previous = current


def extract_context_anchors(sentence: str, target_word: str | None) -> list[str]:
    target_norm = normalize_context_text(target_word or "")
    anchors: list[str] = []
    for token in re.findall(r"[가-힣A-Za-z0-9]+", sentence or ""):
        token = strip_particle(token.strip())
        if len(token) < 2 or token in GENERIC_CONTEXT_WORDS:
            continue
        token_norm = normalize_context_text(token)
        if not token_norm or token_norm == target_norm:
            continue
        if token_norm not in anchors:
            anchors.append(token_norm)
    return anchors[:6]


def preserves_original_context(original_sentence: str, candidate: str, target_word: str | None) -> bool:
    candidate_norm = normalize_context_text(candidate)
    if not candidate_norm:
        return False

    target_norm = normalize_context_text(target_word or "")
    if target_norm and target_norm not in candidate_norm:
        return False

    anchors = extract_context_anchors(original_sentence, target_word)
    if not anchors:
        return True
    return any(anchor in candidate_norm for anchor in anchors)


def split_sentences(text: str) -> list[str]:
    return [
        part.strip()
        for part in re.split(r"[.!?]+", str(text or "").strip())
        if part.strip()
    ]


def transform_sentence_ending(sentence: str, style: str) -> str:
    sentence = sentence.strip().rstrip(".!?")
    if not sentence:
        return sentence

    if style == "formal":
        replacements = [
            ("했습니다", "했습니다"),
            ("했어요", "했습니다"),
            ("했다", "했습니다"),
            ("합니다", "합니다"),
            ("해요", "합니다"),
            ("하다", "합니다"),
            ("입니다", "입니다"),
            ("이에요", "입니다"),
            ("예요", "입니다"),
            ("이다", "입니다"),
            ("있어요", "있습니다"),
            ("있다", "있습니다"),
            ("없어요", "없습니다"),
            ("없다", "없습니다"),
            ("어요", "습니다"),
            ("어", "습니다"),
            ("다", "습니다"),
        ]
    elif style == "smart_casual":
        replacements = [
            ("했습니다", "했어요"),
            ("했다", "했어요"),
            ("합니다", "해요"),
            ("하다", "해요"),
            ("입니다", "이에요"),
            ("이다", "이에요"),
            ("있다", "있어요"),
            ("없다", "없어요"),
            ("다", "어요"),
        ]
    else:
        replacements = [
            ("했습니다", "했어"),
            ("했어요", "했어"),
            ("했다", "했어"),
            ("합니다", "해"),
            ("해요", "해"),
            ("하다", "해"),
            ("입니다", "이야"),
            ("이에요", "이야"),
            ("예요", "야"),
            ("이다", "이야"),
            ("있어요", "있어"),
            ("있다", "있어"),
            ("없어요", "없어"),
            ("없다", "없어"),
            ("어요", "어"),
            ("다", "어"),
        ]

    for old, new in replacements:
        if sentence.endswith(old):
            return sentence[: -len(old)] + new
    return sentence


def transform_register(text: str, style: str) -> str:
    sentence = str(text or "").strip()
    if style == "formal":
        sentence = sentence.replace("나는 ", "저는 ").replace("나 ", "저는 ")
    elif style == "smart_casual":
        sentence = sentence.replace("나는 ", "저는 ").replace("나 ", "저 ")
    else:
        sentence = sentence.replace("저는 ", "나는 ").replace("저 ", "나 ")

    converted = [transform_sentence_ending(part, style) for part in split_sentences(sentence)]
    return ". ".join(part for part in converted if part) + "."


def to_formal_sentence(text: str) -> str:
    return transform_register(text, "formal")


def to_smart_casual_sentence(text: str) -> str:
    return transform_register(text, "smart_casual")


def to_casual_sentence(text: str) -> str:
    return transform_register(text, "casual").rstrip(".")

def detect_meaning_issue(user_sentence: str, target_word: str | None) -> dict | None:
    if target_word != "권선징악":
        return None

    context = str(user_sentence or "").replace("권선징악", "")
    profit_terms = ["이익", "돈", "수익", "재물", "실속"]
    moral_terms = ["선", "악", "착한", "나쁜", "못된", "벌", "징계", "응징", "보상", "권장"]
    has_profit_focus = any(term in context for term in profit_terms)
    has_moral_context = any(term in context for term in moral_terms)

    if has_profit_focus and not has_moral_context:
        return {
            "message": "'권선징악'은 이익을 추구한다는 뜻이 아니라, 착한 일을 권하고 악한 일을 벌한다는 뜻입니다.",
            "suggestion": "착한 사람은 보상받고 악한 사람은 벌받는 것이 권선징악이다.",
        }
    return None

def build_fallback_feedback(user_sentence: str, target_word: str | None, dictionary_docs: list[dict], spoken_result: dict) -> dict:
    corrected = user_sentence
    grammar_status = "correct"
    grammar_message = "문법적으로 큰 오류가 없습니다."
    grammar_suggestion = None

    if "쫒" in corrected:
        corrected = corrected.replace("쫒", "쫓")
        grammar_status = "incorrect"
        grammar_message = "'쫓다'의 활용형은 '쫓는'이 올바른 표기입니다."
        grammar_suggestion = corrected

    if target_word == "정" and "카페를" in user_sentence and "정" in user_sentence:
        corrected = user_sentence.replace("카페를", "카페에")
        grammar_status = "incorrect"
        grammar_message = "'정이 들다'와 함께 쓸 때는 목적격 조사 '를'보다 부사격 조사 '에'가 더 자연스럽습니다."
        grammar_suggestion = corrected
    elif target_word and " " in target_word:
        compact_target = re.sub(r"\s+", "", target_word)
        if compact_target in user_sentence and target_word not in user_sentence:
            corrected = user_sentence.replace(compact_target, target_word)
            grammar_status = "incorrect"
            grammar_message = f"'{target_word}'는 띄어 써야 하는 표현입니다."
            grammar_suggestion = corrected
        elif target_word == "신경 쓰다" and "신경써" in user_sentence:
            corrected = user_sentence.replace("신경써", "신경 써")
            grammar_status = "incorrect"
            grammar_message = "'신경 쓰다'는 활용형에서도 띄어 써야 하므로 '신경 써'가 올바른 표기입니다."
            grammar_suggestion = corrected

    dictionary_summary = build_dictionary_evidence_summary(dictionary_docs)
    spoken_examples = spoken_result.get("examples", [])
    meaning_issue = detect_meaning_issue(user_sentence, target_word)
    meaning_correct = meaning_issue is None
    meaning_message = (
        meaning_issue["message"] if meaning_issue else "대상 문화어휘의 의미는 현재 문맥에서 크게 어긋나지 않습니다."
    )
    meaning_suggestion = meaning_issue["suggestion"] if meaning_issue else None
    base_sentence = meaning_suggestion or (corrected if corrected != user_sentence else user_sentence)
    smart_casual = to_smart_casual_sentence(base_sentence)
    formal = to_formal_sentence(base_sentence)
    casual = to_casual_sentence(base_sentence)
    grammar_reason = build_dictionary_reason(dictionary_summary, grammar_message)
    meaning_reason = build_dictionary_reason(dictionary_summary, meaning_message)
    tpo_reason = build_spoken_reason(spoken_examples)

    return {
        "original_sentence": user_sentence,
        "target_word": target_word or "",
        "grammar": {
            "correct": grammar_status == "correct",
            "reason": grammar_reason,
            "suggestion": grammar_suggestion,
        },
        "meaning": {
            "correct": meaning_correct,
            "reason": meaning_reason,
            "suggestion": meaning_suggestion,
        },
        "tpo": {
            "best_fit": "반격식",
            "reason": tpo_reason,
            "공적": formal,
            "사적": casual,
            "반격식": smart_casual,
        },
        "summary": "문법과 의미를 확인하고, 공적/사적/반격식에 맞는 문장을 짧게 제안했습니다.",
    }


def sanitize_feedback_result(result: dict, user_sentence: str, target_word: str | None, dictionary_docs: list[dict], spoken_result: dict) -> dict:
    if not isinstance(result, dict) or result.get("json_parse_error"):
        return build_fallback_feedback(user_sentence, target_word, dictionary_docs, spoken_result)

    fallback = build_fallback_feedback(user_sentence, target_word, dictionary_docs, spoken_result)
    result["original_sentence"] = user_sentence
    result["target_word"] = target_word or result.get("target_word", "")
    result.setdefault("grammar", fallback["grammar"])
    result.setdefault("meaning", fallback["meaning"])
    result.setdefault("tpo", fallback["tpo"])
    result.setdefault("summary", fallback["summary"])
    result["grammar"].setdefault("correct", fallback["grammar"]["correct"])
    result["grammar"].setdefault("reason", fallback["grammar"]["reason"])
    result["grammar"].setdefault("suggestion", fallback["grammar"]["suggestion"])
    result["meaning"].setdefault("correct", fallback["meaning"]["correct"])
    result["meaning"].setdefault("reason", fallback["meaning"]["reason"])
    result["meaning"].setdefault("suggestion", fallback["meaning"]["suggestion"])
    if fallback["grammar"]["correct"] is False:
        result["grammar"] = fallback["grammar"]
    if fallback["meaning"]["correct"] is False:
        result["meaning"] = fallback["meaning"]
    result["tpo"].setdefault("best_fit", fallback["tpo"]["best_fit"])
    result["tpo"].setdefault("reason", fallback["tpo"]["reason"])
    for key in ["공적", "사적", "반격식"]:
        result["tpo"].setdefault(key, fallback["tpo"][key])
        if not preserves_original_context(user_sentence, str(result["tpo"].get(key, "")), target_word):
            result["tpo"][key] = fallback["tpo"][key]

    if not dictionary_docs:
        result["grammar"]["reason"] = fallback["grammar"]["reason"]
        result["meaning"]["reason"] = fallback["meaning"]["reason"]

    return result


def collect_evidence(user_sentence: str) -> dict:
    target_word = extract_target_word(user_sentence)
    try:
        dictionary_docs = search_dictionary_documents_balanced(user_sentence, top_k=6)
    except Exception:
        dictionary_docs = []

    try:
        spoken_result = search_spoken_examples(user_sentence, target_word=target_word, top_k=5)
    except Exception:
        spoken_result = {
            "query": user_sentence,
            "target_word": target_word or "",
            "keywords": [],
            "examples": [],
        }

    return {
        "target_word": target_word,
        "dictionary_docs": dictionary_docs,
        "spoken_result": spoken_result,
    }


def generate_feedback(user_sentence: str) -> dict:
    settings = load_settings()
    evidence = collect_evidence(user_sentence)
    target_word = evidence["target_word"]
    dictionary_docs = evidence["dictionary_docs"]
    spoken_result = evidence["spoken_result"]

    if settings["chat_provider"] == "gemini" and not settings["gemini_api_key"]:
        return build_fallback_feedback(user_sentence, target_word, dictionary_docs, spoken_result)

    if settings["chat_provider"] == "openai" and not settings["openai_api_key"]:
        return build_fallback_feedback(user_sentence, target_word, dictionary_docs, spoken_result)

    try:
        if settings["chat_provider"] == "gemini":
            return generate_feedback_with_gemini(user_sentence, target_word, dictionary_docs, spoken_result, settings)
        return generate_feedback_with_openai(user_sentence, target_word, dictionary_docs, spoken_result, settings)
    except Exception:
        return build_fallback_feedback(user_sentence, target_word, dictionary_docs, spoken_result)


def generate_feedback_with_openai(user_sentence: str, target_word: str | None, dictionary_docs: list[dict], spoken_result: dict, settings: dict) -> dict:
    from openai import OpenAI

    client = OpenAI(api_key=settings["openai_api_key"])
    try:
        response = client.chat.completions.create(
            model=settings["chat_model"],
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": build_user_prompt(user_sentence, dictionary_docs, spoken_result, target_word),
                },
            ],
            temperature=0.2,
            response_format={"type": "json_object"},
        )
        parsed = parse_model_json(response.choices[0].message.content or "")
    except Exception as exc:
        if is_quota_error(exc):
            return build_fallback_feedback(user_sentence, target_word, dictionary_docs, spoken_result)
        raise

    return sanitize_feedback_result(parsed, user_sentence, target_word, dictionary_docs, spoken_result)


def generate_feedback_with_gemini(user_sentence: str, target_word: str | None, dictionary_docs: list[dict], spoken_result: dict, settings: dict) -> dict:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=settings["gemini_api_key"])
    try:
        response = client.models.generate_content(
            model=settings["gemini_chat_model"],
            contents=build_user_prompt(user_sentence, dictionary_docs, spoken_result, target_word),
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                response_mime_type="application/json",
                temperature=0.2,
            ),
        )
        parsed = parse_model_json(response.text or "")
    except Exception:
        return build_fallback_feedback(user_sentence, target_word, dictionary_docs, spoken_result)

    return sanitize_feedback_result(parsed, user_sentence, target_word, dictionary_docs, spoken_result)


def main() -> None:
    result = generate_feedback(DEFAULT_SENTENCE)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
