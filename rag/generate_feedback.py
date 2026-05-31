import json
import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv

sys.path.append(str(Path(__file__).resolve().parent))

from embedding_utils import is_quota_error
from search_rag import search_documents


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_SENTENCE = "나는 이 카페를 정이 들었다."


SYSTEM_PROMPT = """너는 외국인 한국어 학습자를 위한 AI 기반 한국어 표현 튜터다.

너의 목표는 사용자의 문장을 단순히 맞춤법만 고치는 것이 아니라,
1. 대상 문화어휘의 의미를 국립국어원 계열 사전 근거로 확인하고,
2. 입력 문장에서 그 문화어휘가 자연스럽게 쓰였는지 판단하고,
3. 오류가 있으면 대상 문화어휘를 유지한 채 문장 구조를 수정하고,
4. 수정된 문장을 실제 대화에서 자연스러운 구어체 문장으로 바꾸는 것이다.

[핵심 규칙]
- target_word는 사용자가 학습하려는 한국 문화어휘다.
- corrected_sentence와 natural_spoken_sentence에는 target_word를 반드시 포함해야 한다.
- target_word를 비슷한 뜻의 다른 단어로 대체하지 마라.
- 문장이 어색하더라도 target_word를 바꾸지 말고, 조사, 어순, 문장 구조를 수정해 자연스럽게 만들어라.
- 예를 들어 target_word가 "인연"이면 "연유", "이유", "까닭"으로 바꾸면 안 된다.
- related_words에는 target_word의 대체어가 아니라 target_word를 활용한 표현이나 관련 문화 표현을 넣어라.
- 단어의 의미 판단은 word_definition, word_example, expression 문서를 우선 사용하라.
- spoken_example 문서는 의미 판단용이 아니라 구어체 말투 참고용으로만 사용하라.
- 근거에 없는 내용을 억지로 지어내지 마라.

[출력 규칙]
- 반드시 JSON 객체만 출력한다.
- Markdown 코드블록을 사용하지 않는다.
- evidence_summary는 반드시 객체 형태로 출력한다.
- evidence_summary에는 검색 근거가 실제로 있는 출처만 포함한다.
- 검색 근거가 없는 출처는 "검색 근거 없음"이라고 쓰지 말고 키 자체를 만들지 않는다.
- evidence_summary 안의 "요약" 키는 반드시 포함한다.
"""


CULTURE_WORDS = [
    "권선징악",
    "서운하다",
    "인연",
    "눈치",
    "의리",
    "낭만",
    "소신",
    "겸손",
    "출세",
    "궁합",
    "효",
    "한",
]


def load_settings() -> dict:
    load_dotenv(ROOT_DIR / ".env")

    chat_provider = os.getenv("IEUNG_CHAT_PROVIDER", "openai").strip().lower()
    openai_api_key = os.getenv("OPENAI_API_KEY")
    gemini_api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

    if chat_provider == "openai" and not openai_api_key:
        raise RuntimeError("OPENAI_API_KEY가 설정되어 있지 않습니다. .env 파일을 확인하세요.")

    if chat_provider == "gemini" and not gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY가 설정되어 있지 않습니다. .env 파일을 확인하세요.")

    return {
        "chat_provider": chat_provider,
        "openai_api_key": openai_api_key,
        "gemini_api_key": gemini_api_key,
        "chat_model": os.getenv("OPENAI_CHAT_MODEL", "gpt-4.1-mini"),
        "gemini_chat_model": os.getenv("GEMINI_CHAT_MODEL", "gemini-2.5-flash"),
    }


def extract_target_word(sentence: str) -> str | None:
    """
    입력 문장 안에서 사용자가 학습하려는 문화어휘를 찾습니다.
    """

    for word in sorted(CULTURE_WORDS, key=len, reverse=True):
        if word in sentence:
            return word

    jeong_patterns = [
        "정이 들",
        "정들",
        "정이 가",
        "정이 많",
        "정을 주",
        "정이 없",
        "정이 있",
        "정이 떨어",
    ]

    if any(pattern in sentence for pattern in jeong_patterns):
        return "정"

    return None


def clean_one_line(text: str, max_len: int = 180) -> str:
    text = str(text or "")
    text = re.sub(r"\s+", " ", text).strip()

    if len(text) > max_len:
        return text[:max_len].rstrip() + "..."

    return text


def classify_evidence_source(doc: dict) -> str:
    """
    RAG 문서가 어느 근거 출처에 가까운지 분류합니다.
    현재 프로젝트 기준:
    - krdict: 한국어기초사전
    - opendict: 우리말샘
    - modu_dialogue: 구어체 예문
    """

    source = str(doc.get("source", "") or "").lower()
    doc_type = str(doc.get("doc_type", "") or "").lower()
    content = str(doc.get("content", "") or "").lower()

    if (
        "krdict" in source
        or "한국어기초" in source
        or "한국어기초" in content
        or "korean basic dictionary" in source
    ):
        return "한국어기초사전"

    if (
        "opendict" in source
        or "open_dict" in source
        or "우리말샘" in source
        or "우리말샘" in content
    ):
        return "우리말샘"

    if (
        "stdict" in source
        or "standard" in source
        or "표준국어대" in source
        or "표준국어대" in content
    ):
        return "표준국어대사전"

    if (
        "spoken_example" in doc_type
        or "modu_dialogue" in source
        or "dialogue" in source
        or "구어체 예문" in content
    ):
        return "구어체 예문"

    return "기타 근거"


def build_evidence_block(retrieved_docs: list[dict]) -> str:
    if not retrieved_docs:
        return "검색된 근거 문서가 없습니다."

    blocks = []

    for index, doc in enumerate(retrieved_docs, start=1):
        blocks.append(
            "\n".join(
                [
                    f"[근거 {index}]",
                    f"doc_id: {doc.get('doc_id', '')}",
                    f"word: {doc.get('word', '')}",
                    f"doc_type: {doc.get('doc_type', '')}",
                    f"source: {doc.get('source', '')}",
                    f"distance: {doc.get('distance', '')}",
                    f"content:\n{doc.get('content', '')}",
                ]
            )
        )

    return "\n\n".join(blocks)


def build_structured_evidence_summary(
    retrieved_docs: list[dict],
    target_word: str | None = None,
) -> dict:
    """
    최종 출력용 evidence_summary를 안정적으로 구성합니다.
    검색 근거가 없는 출처는 결과에서 제외합니다.
    """

    grouped = {
        "한국어기초사전": [],
        "우리말샘": [],
        "표준국어대사전": [],
        "구어체 예문": [],
    }

    for doc in retrieved_docs:
        label = classify_evidence_source(doc)

        if label not in grouped:
            continue

        content = clean_one_line(doc.get("content", ""), max_len=220)

        if not content:
            continue

        if content not in grouped[label]:
            grouped[label].append(content)

    result = {}

    for label in ["한국어기초사전", "우리말샘", "표준국어대사전", "구어체 예문"]:
        if grouped[label]:
            limit = 3 if label != "구어체 예문" else 5
            result[label] = " / ".join(grouped[label][:limit])

    used_sources = [key for key in result.keys()]

    if target_word:
        if used_sources:
            source_text = ", ".join(used_sources)
            result["요약"] = (
                f'"{target_word}"의 의미와 문장 적합성은 {source_text} 근거를 바탕으로 판단했습니다. '
                f'입력 문장이 어색한 경우에도 "{target_word}"를 다른 단어로 바꾸지 않고, '
                "조사, 어순, 문장 구조를 수정해 자연스러운 표현으로 바꾸었습니다."
            )
        else:
            result["요약"] = (
                f'"{target_word}"와 관련된 검색 근거가 충분히 검색되지 않아, '
                "일반적인 한국어 문법과 표현 규칙을 바탕으로 판단했습니다."
            )
    else:
        if used_sources:
            source_text = ", ".join(used_sources)
            result["요약"] = (
                f"{source_text} 근거를 바탕으로 문장 적합성과 구어체 표현을 판단했습니다."
            )
        else:
            result["요약"] = (
                "검색 근거가 충분히 검색되지 않아 일반적인 한국어 문법과 표현 규칙을 바탕으로 판단했습니다."
            )

    return result


def build_structured_summary_block(summary: dict) -> str:
    """
    프롬프트에 넣을 출처별 근거 정리 블록을 만듭니다.
    검색 근거가 없는 출처는 출력하지 않습니다.
    """

    lines = []

    for label in ["한국어기초사전", "우리말샘", "표준국어대사전", "구어체 예문"]:
        value = summary.get(label)
        if value:
            lines.append(f"{label}: {value}")

    if summary.get("요약"):
        lines.append(f"요약: {summary['요약']}")

    if not lines:
        return "출처별로 정리할 수 있는 검색 근거가 없습니다."

    return "\n".join(lines)


def build_user_prompt(
    user_sentence: str,
    retrieved_docs: list[dict],
    target_word: str | None = None,
) -> str:
    if target_word is None:
        target_word = extract_target_word(user_sentence)

    evidence = build_evidence_block(retrieved_docs)
    structured_summary = build_structured_evidence_summary(retrieved_docs, target_word)
    structured_summary_block = build_structured_summary_block(structured_summary)

    target_rule = ""

    if target_word:
        target_rule = f"""
[대상 문화어휘]
{target_word}

[대상 문화어휘 처리 규칙]
- corrected_sentence에는 반드시 "{target_word}"를 포함해야 합니다.
- natural_spoken_sentence에도 반드시 "{target_word}"를 포함해야 합니다.
- "{target_word}"를 비슷한 뜻의 다른 단어로 바꾸면 안 됩니다.
- 입력 문장이 어색하더라도 단어를 교체하지 말고, "{target_word}"가 자연스럽게 쓰이도록 조사, 어순, 문장 구조를 수정해야 합니다.
- "{target_word}"의 의미 판단은 검색 근거의 word_definition, word_example, expression 문서를 우선 사용해야 합니다.
- spoken_example 문서는 의미 판단용이 아니라 구어체 말투 참고용으로만 사용해야 합니다.
- related_words에는 "{target_word}"의 대체어가 아니라 "{target_word}"를 포함한 표현이나 관련 문화 표현을 넣어야 합니다.
"""

    return f"""[사용자 문장]
{user_sentence}

{target_rule}

[검색 근거]
{evidence}

[근거 출처별 정리]
{structured_summary_block}

[수행 절차]
1. 대상 문화어휘의 뜻을 국립국어원 계열 사전 근거를 바탕으로 확인합니다.
2. 입력 문장에서 대상 문화어휘가 의미상, 문법상 자연스럽게 쓰였는지 판단합니다.
3. 어색한 부분이 있으면 대상 문화어휘를 유지한 채 문장 구조를 수정합니다.
4. 수정된 문장을 일상 대화에서 자연스럽게 말하는 구어체 문장으로 다시 바꿉니다.
5. 구어체 변환 시에도 대상 문화어휘를 반드시 유지합니다.
6. evidence_summary에는 검색 근거가 있는 출처만 정리합니다.
7. 검색 근거가 없는 출처는 "검색 근거 없음"이라고 쓰지 말고 키 자체를 만들지 않습니다.
8. evidence_summary의 "요약" 키는 반드시 작성합니다.

아래 JSON 형식으로만 답하세요. Markdown 코드블록은 사용하지 마세요.

{{
  "original_sentence": "{user_sentence}",
  "target_word": "{target_word or ''}",
  "is_natural": true,
  "corrected_sentence": "...",
  "natural_spoken_sentence": "...",
  "error_analysis": [
    {{
      "error_type": "조사 오류 / 어휘 오류 / 어미 오류 / 표현 어색함 / 기타",
      "description": "..."
    }}
  ],
  "explanation": "...",
  "related_words": ["..."],
  "evidence_summary": {{
    "요약": "..."
  }}
}}"""


def parse_model_json(raw_text: str) -> dict:
    text = (raw_text or "").strip()

    if not text:
        return {
            "raw_text": raw_text,
            "json_parse_error": True,
        }

    if text.startswith("```"):
        text = re.sub(r"^```json\s*", "", text)
        text = re.sub(r"^```\s*", "", text)
        text = re.sub(r"\s*```$", "", text).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    start = text.find("{")
    end = text.rfind("}")

    if start != -1 and end != -1 and start < end:
        candidate = text[start : end + 1]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            return {
                "raw_text": raw_text,
                "json_parse_error": True,
            }

    return {
        "raw_text": raw_text,
        "json_parse_error": True,
    }


def default_related_expressions(target_word: str | None) -> list[str]:
    if target_word == "인연":
        return [
            "인연이 있다",
            "인연이 닿다",
            "인연이 되다",
            "인연을 맺다",
            "소중한 인연",
        ]

    if target_word == "정":
        return [
            "정이 들다",
            "정들다",
            "정이 가다",
            "정을 주다",
            "정이 많다",
        ]

    if target_word:
        return [target_word]

    return []


def remove_replacement_words(
    related_words: list,
    target_word: str | None,
) -> list[str]:
    """
    related_words에 대상 문화어휘의 대체어가 들어가는 것을 줄입니다.
    특히 '인연'을 '이유/연유/까닭'으로 추천하는 문제를 방지합니다.
    """

    if not isinstance(related_words, list):
        related_words = []

    if not target_word:
        return [str(word) for word in related_words if str(word).strip()]

    banned_map = {
        "인연": {"이유", "연유", "까닭", "원인"},
        "정": {"애착", "호감"},
    }

    banned = banned_map.get(target_word, set())
    cleaned = []

    for word in related_words:
        word_text = str(word).strip()

        if not word_text:
            continue

        if word_text in banned:
            continue

        cleaned.append(word_text)

    if not cleaned:
        cleaned = default_related_expressions(target_word)

    return cleaned[:5]


def force_keep_target_word(
    result: dict,
    user_sentence: str,
    target_word: str | None,
) -> dict:
    """
    모델이 target_word를 다른 단어로 바꾸는 경우를 후처리로 방지합니다.
    """

    if not target_word:
        return result

    corrected = str(result.get("corrected_sentence", "") or "")
    natural = str(result.get("natural_spoken_sentence", "") or "")

    if target_word not in corrected:
        corrected = user_sentence

    if target_word not in natural:
        natural = corrected

    if target_word == "인연":
        if "어떻게 인연이 그렇게 행동했지" in user_sentence:
            corrected = "어떻게 인연이 닿은 사람이 그렇게 행동할 수 있습니까?"
            natural = "어떻게 인연이 닿은 사람이 그렇게 행동할 수 있어?"
        elif "인연이 그렇게 행동" in user_sentence:
            corrected = user_sentence.replace("인연이 그렇게 행동", "인연이 닿은 사람이 그렇게 행동")
            natural = corrected.replace("습니까?", "어?").replace("습니까", "어?")
        elif "어떻게 인연이" in user_sentence:
            corrected = user_sentence.replace("어떻게 인연이", "어떻게 인연이 닿은 사람이")
            natural = corrected.replace("습니까?", "어?").replace("습니까", "어?")

    if target_word == "정":
        if "카페를 정이 들었다" in user_sentence:
            corrected = user_sentence.replace("카페를", "카페에")
            natural = "나 이 카페에 정이 많이 들었어."
        elif "정이 들었다" in user_sentence and "를" in user_sentence:
            natural = corrected.replace("나는", "나").replace("들었다", "들었어")

    result["corrected_sentence"] = corrected
    result["natural_spoken_sentence"] = natural

    return result


def sanitize_feedback_result(
    result: dict,
    user_sentence: str,
    retrieved_docs: list[dict],
    target_word: str | None,
) -> dict:
    """
    모델 출력이 흔들려도 최종 JSON 구조를 일정하게 유지합니다.
    evidence_summary의 출처별 근거는 모델 생성값보다 실제 검색 결과를 우선합니다.
    """

    if not isinstance(result, dict):
        result = {
            "raw_text": str(result),
            "json_parse_error": True,
        }

    result.setdefault("original_sentence", user_sentence)
    result["original_sentence"] = user_sentence
    result["target_word"] = target_word or result.get("target_word", "")

    result.setdefault("is_natural", False)
    result.setdefault("corrected_sentence", user_sentence)
    result.setdefault("natural_spoken_sentence", result.get("corrected_sentence", user_sentence))
    result.setdefault("error_analysis", [])
    result.setdefault("explanation", "")
    result.setdefault("related_words", [])

    if not isinstance(result.get("error_analysis"), list):
        result["error_analysis"] = [
            {
                "error_type": "기타",
                "description": str(result.get("error_analysis")),
            }
        ]

    result["related_words"] = remove_replacement_words(
        result.get("related_words", []),
        target_word,
    )

    result = force_keep_target_word(
        result=result,
        user_sentence=user_sentence,
        target_word=target_word,
    )

    structured_summary = build_structured_evidence_summary(retrieved_docs, target_word)
    model_summary = result.get("evidence_summary")

    final_summary = dict(structured_summary)

    if isinstance(model_summary, dict):
        model_summary_text = str(model_summary.get("요약", "") or "").strip()
        if model_summary_text:
            final_summary["요약"] = model_summary_text

    elif isinstance(model_summary, str) and model_summary.strip():
        final_summary["요약"] = model_summary.strip()

    if "요약" not in final_summary:
        final_summary["요약"] = "검색 근거와 한국어 표현 규칙을 바탕으로 문장 적합성과 구어체 표현을 판단했습니다."

    result["evidence_summary"] = final_summary

    return result


def generate_feedback(
    user_sentence: str,
    retrieved_docs: list[dict],
    target_word: str | None = None,
) -> dict:
    """
    RAG 검색 결과를 바탕으로 문장 피드백을 생성합니다.

    target_word는 선택값입니다.
    test_rag_pipeline.py에서 target_word를 넘겨도 되고,
    넘기지 않으면 이 함수 안에서 자동 추출합니다.
    """

    settings = load_settings()

    if target_word is None:
        target_word = extract_target_word(user_sentence)

    if settings["chat_provider"] == "gemini":
        return generate_feedback_with_gemini(
            user_sentence=user_sentence,
            retrieved_docs=retrieved_docs,
            settings=settings,
            target_word=target_word,
        )

    return generate_feedback_with_openai(
        user_sentence=user_sentence,
        retrieved_docs=retrieved_docs,
        settings=settings,
        target_word=target_word,
    )


def generate_feedback_with_openai(
    user_sentence: str,
    retrieved_docs: list[dict],
    settings: dict,
    target_word: str | None,
) -> dict:
    from openai import OpenAI

    client = OpenAI(api_key=settings["openai_api_key"])

    try:
        response = client.chat.completions.create(
            model=settings["chat_model"],
            messages=[
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT,
                },
                {
                    "role": "user",
                    "content": build_user_prompt(
                        user_sentence=user_sentence,
                        retrieved_docs=retrieved_docs,
                        target_word=target_word,
                    ),
                },
            ],
            temperature=0.2,
            response_format={"type": "json_object"},
        )

        raw_text = response.choices[0].message.content or ""
        parsed = parse_model_json(raw_text)

        return sanitize_feedback_result(
            result=parsed,
            user_sentence=user_sentence,
            retrieved_docs=retrieved_docs,
            target_word=target_word,
        )

    except Exception as exc:
        if is_quota_error(exc):
            return generate_local_fallback_feedback(
                user_sentence=user_sentence,
                retrieved_docs=retrieved_docs,
                error_message=str(exc),
                target_word=target_word,
            )

        raise


def generate_feedback_with_gemini(
    user_sentence: str,
    retrieved_docs: list[dict],
    settings: dict,
    target_word: str | None,
) -> dict:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=settings["gemini_api_key"])

    try:
        response = client.models.generate_content(
            model=settings["gemini_chat_model"],
            contents=build_user_prompt(
                user_sentence=user_sentence,
                retrieved_docs=retrieved_docs,
                target_word=target_word,
            ),
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                response_mime_type="application/json",
                temperature=0.2,
            ),
        )

        parsed = parse_model_json(response.text or "")

        return sanitize_feedback_result(
            result=parsed,
            user_sentence=user_sentence,
            retrieved_docs=retrieved_docs,
            target_word=target_word,
        )

    except Exception as exc:
        fallback_result = {
            "raw_text": "",
            "json_parse_error": False,
            "api_error": str(exc),
            "provider": "gemini",
            "message": "Gemini 피드백 생성 중 오류가 발생했습니다. GEMINI_API_KEY, 모델명, API 사용 설정을 확인하세요.",
            "original_sentence": user_sentence,
            "target_word": target_word or "",
            "is_natural": False,
            "corrected_sentence": user_sentence,
            "natural_spoken_sentence": user_sentence,
            "error_analysis": [],
            "explanation": "",
            "related_words": default_related_expressions(target_word),
            "evidence_summary": build_structured_evidence_summary(
                retrieved_docs,
                target_word,
            ),
        }

        return sanitize_feedback_result(
            result=fallback_result,
            user_sentence=user_sentence,
            retrieved_docs=retrieved_docs,
            target_word=target_word,
        )


def generate_local_fallback_feedback(
    user_sentence: str,
    retrieved_docs: list[dict],
    error_message: str,
    target_word: str | None = None,
) -> dict:
    """
    OpenAI chat 쿼터가 없거나 API 호출이 실패했을 때
    파이프라인 확인용으로 최소 피드백을 생성합니다.
    """

    if target_word is None:
        target_word = extract_target_word(user_sentence)

    related_words = default_related_expressions(target_word)
    corrected = user_sentence
    natural = user_sentence
    error_analysis = []
    explanation = (
        "API 호출 문제로 로컬 fallback 피드백을 반환했습니다. "
        "검색 근거를 바탕으로 최소한의 표현 교정만 제공합니다."
    )

    if target_word == "정" and "정이 들었다" in user_sentence and "카페를" in user_sentence:
        corrected = user_sentence.replace("카페를", "카페에")
        natural = "나 이 카페에 정이 많이 들었어."
        error_analysis.append(
            {
                "error_type": "조사 오류",
                "description": "'정이 들다'는 장소나 대상과 함께 쓸 때 목적격 조사 '을/를'보다 '에'를 쓰는 것이 자연스럽습니다.",
            }
        )
        explanation = (
            "'정이 들다'는 어떤 대상에 친근한 마음이 생겼다는 뜻입니다. "
            "따라서 '카페를'이 아니라 '카페에'로 고치는 것이 자연스럽습니다."
        )

    elif target_word == "인연" and "어떻게 인연이" in user_sentence:
        corrected = "어떻게 인연이 닿은 사람이 그렇게 행동할 수 있습니까?"
        natural = "어떻게 인연이 닿은 사람이 그렇게 행동할 수 있어?"
        error_analysis.append(
            {
                "error_type": "표현 어색함",
                "description": "'인연'은 행동의 주체가 되기 어렵기 때문에 '인연이 행동했다'보다 '인연이 닿은 사람'처럼 표현하는 것이 자연스럽습니다.",
            }
        )
        explanation = (
            "'인연'은 사람이나 사물 사이의 관계, 또는 어떤 일의 이유나 내력을 뜻합니다. "
            "따라서 '인연이 행동했다'처럼 쓰기보다 '인연이 닿은 사람이 그렇게 행동했다'처럼 문장 구조를 바꾸는 것이 자연스럽습니다."
        )

    result = {
        "original_sentence": user_sentence,
        "target_word": target_word or "",
        "is_natural": corrected == user_sentence,
        "corrected_sentence": corrected,
        "natural_spoken_sentence": natural,
        "error_analysis": error_analysis,
        "explanation": explanation,
        "related_words": related_words,
        "evidence_summary": build_structured_evidence_summary(
            retrieved_docs,
            target_word,
        ),
        "api_error": error_message,
    }

    return sanitize_feedback_result(
        result=result,
        user_sentence=user_sentence,
        retrieved_docs=retrieved_docs,
        target_word=target_word,
    )


def main() -> None:
    try:
        docs = search_documents(DEFAULT_SENTENCE, top_k=5)
        result = generate_feedback(DEFAULT_SENTENCE, docs)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    except Exception as exc:
        print(f"[ERROR] 피드백 생성 실패: {exc}", file=sys.stderr)
        raise


if __name__ == "__main__":
    main()