import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

sys.path.append(str(Path(__file__).resolve().parent))
from embedding_utils import is_quota_error
from search_rag import search_documents


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_SENTENCE = "나는 이 카페를 정이 들었다."


SYSTEM_PROMPT = """너는 외국인 한국어 학습자를 위한 AI 기반 한국어 표현 튜터다.
너의 목표는 사용자의 문장을 단순히 맞춤법만 고치는 것이 아니라, 한국인이 실제로 사용하는 자연스러운 표현으로 바꾸고, 왜 그렇게 고치는지 쉽게 설명하는 것이다.
반드시 제공된 근거를 우선적으로 사용하되, 근거에 없는 내용을 억지로 지어내지 마라."""


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
                    f"source: {doc.get('source', '')}",
                    f"content:\n{doc.get('content', '')}",
                ]
            )
        )
    return "\n\n".join(blocks)


def build_user_prompt(user_sentence: str, retrieved_docs: list[dict]) -> str:
    evidence = build_evidence_block(retrieved_docs)
    return f"""[사용자 문장]
{user_sentence}

[근거]
{evidence}

아래 JSON 형식으로만 답해라. Markdown 코드블록은 사용하지 마라.
{{
  "original_sentence": "...",
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
  "evidence_summary": "..."
}}"""


def parse_model_json(raw_text: str) -> dict:
    text = raw_text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:].strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"raw_text": raw_text, "json_parse_error": True}


def generate_feedback(user_sentence: str, retrieved_docs: list) -> dict:
    settings = load_settings()
    if settings["chat_provider"] == "gemini":
        return generate_feedback_with_gemini(user_sentence, retrieved_docs, settings)
    return generate_feedback_with_openai(user_sentence, retrieved_docs, settings)


def generate_feedback_with_openai(user_sentence: str, retrieved_docs: list, settings: dict) -> dict:
    client = OpenAI(api_key=settings["openai_api_key"])
    try:
        response = client.chat.completions.create(
            model=settings["chat_model"],
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": build_user_prompt(user_sentence, retrieved_docs)},
            ],
            temperature=0.2,
            response_format={"type": "json_object"},
        )
        raw_text = response.choices[0].message.content or ""
        return parse_model_json(raw_text)
    except Exception as exc:
        if is_quota_error(exc):
            return generate_local_fallback_feedback(user_sentence, retrieved_docs, str(exc))
        raise


def generate_feedback_with_gemini(user_sentence: str, retrieved_docs: list, settings: dict) -> dict:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=settings["gemini_api_key"])
    try:
        response = client.models.generate_content(
            model=settings["gemini_chat_model"],
            contents=build_user_prompt(user_sentence, retrieved_docs),
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                response_mime_type="application/json",
                temperature=0.2,
            ),
        )
        return parse_model_json(response.text or "")
    except Exception as exc:
        return {
            "raw_text": "",
            "json_parse_error": False,
            "api_error": str(exc),
            "provider": "gemini",
            "message": "Gemini 피드백 생성 중 오류가 발생했습니다. GEMINI_API_KEY, 모델명, API 사용 설정을 확인하세요.",
        }


def generate_local_fallback_feedback(user_sentence: str, retrieved_docs: list, error_message: str) -> dict:
    """OpenAI chat 쿼터가 없을 때 파이프라인 확인용으로 최소 피드백을 생성한다."""
    related_words = []
    for doc in retrieved_docs:
        word = doc.get("word")
        if word and word not in related_words:
            related_words.append(word)

    corrected = user_sentence
    natural = user_sentence
    error_analysis = []
    if "정이 들었다" in user_sentence and "카페를" in user_sentence:
        corrected = user_sentence.replace("카페를", "카페에")
        natural = "여기 자주 오다 보니까 정들었어요."
        error_analysis.append(
            {
                "error_type": "조사 오류",
                "description": "'정이 들다'는 장소와 함께 쓸 때 '을/를'보다 '에'를 쓰는 것이 자연스럽습니다.",
            }
        )

    return {
        "original_sentence": user_sentence,
        "is_natural": corrected == user_sentence,
        "corrected_sentence": corrected,
        "natural_spoken_sentence": natural,
        "error_analysis": error_analysis,
        "explanation": "OpenAI API 쿼터 부족으로 로컬 fallback 피드백을 반환했습니다. 검색 근거를 바탕으로 최소한의 표현 교정만 제공합니다.",
        "related_words": related_words[:5],
        "evidence_summary": "검색된 RAG 문서를 사용했지만, 최종 설명 생성은 OpenAI 쿼터 부족으로 규칙 기반 fallback이 처리했습니다.",
        "api_error": error_message,
    }


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
