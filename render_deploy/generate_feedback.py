from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent
sys.path.append(str(ROOT_DIR / "dictionary_pipeline" / "retrieval"))
sys.path.append(str(ROOT_DIR / "spoken_labeling"))

try:
    from embedding_utils import is_quota_error
except Exception:
    def is_quota_error(_exc) -> bool:
        return False


try:
    from search_dictionary_rag import extract_target_word, search_dictionary_documents_balanced
except Exception:
    CULTURE_WORDS = [
        "권선징악",
        "서운하다",
        "정",
        "눈치",
        "인연",
        "의리",
        "효",
        "한",
        "낭만",
        "소신",
        "출세",
        "궁합",
    ]

    def extract_target_word(sentence: str) -> str | None:
        for word in sorted(CULTURE_WORDS, key=len, reverse=True):
            if word in sentence:
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
    if not parts:
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


def to_formal_sentence(text: str) -> str:
    sentence = str(text or "").strip().rstrip(".!?")
    sentence = sentence.replace("나는 ", "저는 ").replace("저 ", "저는 ").replace("나 ", "저는 ")
    sentence = sentence.replace(" 들었어", " 들었습니다")
    sentence = sentence.replace(" 있어?", " 있습니다.")
    if sentence.endswith("들었다"):
        sentence = sentence[:-3] + "들었습니다."
    elif sentence.endswith("했다"):
        sentence = sentence[:-2] + "했습니다."
    elif sentence.endswith("어"):
        sentence = sentence[:-1] + "습니다."
    elif sentence.endswith("어요"):
        sentence = sentence[:-2] + "습니다."
    elif sentence.endswith("요"):
        sentence = sentence[:-1] + "니다."
    else:
        sentence = sentence + "."
    return sentence


def to_smart_casual_sentence(text: str) -> str:
    sentence = str(text or "").strip().rstrip(".!?")
    sentence = sentence.replace("나는 ", "저는 ").replace("나 ", "저 ")
    sentence = sentence.replace(" 들었어", " 들었어요")
    if sentence.endswith("들었다"):
        sentence = sentence[:-3] + "들었어요."
    elif sentence.endswith("했다"):
        sentence = sentence[:-2] + "했어요."
    elif sentence.endswith("어"):
        sentence = sentence[:-1] + "어요."
    elif sentence.endswith("다"):
        sentence = sentence[:-1] + "어요."
    else:
        sentence = sentence + "."
    return sentence


def to_casual_sentence(text: str) -> str:
    sentence = str(text or "").strip().rstrip(".!?")
    sentence = sentence.replace("저는 ", "나는 ").replace("저 ", "나 ")
    sentence = sentence.replace(" 들었습니다", " 들었어").replace(" 들었어요", " 들었어")
    sentence = sentence.replace("입니다.", "이야.")
    if sentence.endswith("들었다"):
        sentence = sentence[:-3] + "들었어"
    return sentence


def build_fallback_feedback(user_sentence: str, target_word: str | None, dictionary_docs: list[dict], spoken_result: dict) -> dict:
    corrected = user_sentence
    grammar_status = "correct"
    grammar_message = "문법적으로 큰 오류가 없습니다."
    grammar_suggestion = None

    if target_word == "정" and "카페를" in user_sentence and "정" in user_sentence:
        corrected = user_sentence.replace("카페를", "카페에")
        grammar_status = "incorrect"
        grammar_message = "'정이 들다'와 함께 쓸 때는 목적격 조사 '를'보다 부사격 조사 '에'가 더 자연스럽습니다."
        grammar_suggestion = corrected

    dictionary_summary = build_dictionary_evidence_summary(dictionary_docs)
    spoken_examples = spoken_result.get("examples", [])
    base_sentence = corrected if corrected != user_sentence else user_sentence
    smart_casual = to_smart_casual_sentence(base_sentence)
    formal = to_formal_sentence(base_sentence)
    casual = to_casual_sentence(base_sentence)
    grammar_reason = build_dictionary_reason(dictionary_summary, grammar_message)
    meaning_reason = build_dictionary_reason(dictionary_summary, "대상 문화어휘의 의미는 현재 문맥에서 크게 어긋나지 않습니다.")
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
            "correct": True,
            "reason": meaning_reason,
            "suggestion": None,
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
    result["tpo"].setdefault("best_fit", fallback["tpo"]["best_fit"])
    result["tpo"].setdefault("reason", fallback["tpo"]["reason"])
    for key in ["공적", "사적", "반격식"]:
        result["tpo"].setdefault(key, fallback["tpo"][key])

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
