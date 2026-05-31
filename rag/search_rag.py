import os
import sys
from pathlib import Path

import chromadb
from dotenv import load_dotenv
from openai import OpenAI

from embedding_utils import is_quota_error, local_embedding


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_QUERY = "나는 이 카페를 정이 들었다."


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


def resolve_project_path(value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = ROOT_DIR / path
    return path


def load_settings() -> dict:
    load_dotenv(ROOT_DIR / ".env")

    embedding_provider = os.getenv("IEUNG_EMBEDDING_PROVIDER", "openai").strip().lower()

    openai_api_key = os.getenv("OPENAI_API_KEY")
    gemini_api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

    if embedding_provider == "openai" and not openai_api_key:
        raise RuntimeError("OPENAI_API_KEY가 설정되어 있지 않습니다. .env 파일을 확인하세요.")

    if embedding_provider == "gemini" and not gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY가 설정되어 있지 않습니다. .env 파일을 확인하세요.")

    if embedding_provider not in {"openai", "gemini", "local"}:
        raise RuntimeError(
            "지원하지 않는 임베딩 provider입니다. "
            "IEUNG_EMBEDDING_PROVIDER 값을 openai, gemini, local 중 하나로 설정하세요."
        )

    return {
        "openai_api_key": openai_api_key,
        "gemini_api_key": gemini_api_key,
        "embedding_provider": embedding_provider,
        "embedding_model": os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"),
        "gemini_embedding_model": os.getenv("GEMINI_EMBEDDING_MODEL", "gemini-embedding-001"),
        "persist_dir": resolve_project_path(os.getenv("CHROMA_PERSIST_DIR", "./chroma_db")),
        "collection_name": os.getenv("CHROMA_COLLECTION_NAME", "ieung_rag"),
    }


def create_gemini_client(api_key: str):
    from google import genai

    return genai.Client(api_key=api_key)


def embed_query(
    *,
    openai_client: OpenAI | None,
    gemini_client,
    provider: str,
    openai_model: str,
    gemini_model: str,
    query: str,
) -> list[float]:
    if provider == "local":
        return local_embedding(query)

    if provider == "gemini":
        from google.genai import types

        response = gemini_client.models.embed_content(
            model=gemini_model,
            contents=query,
            config=types.EmbedContentConfig(task_type="RETRIEVAL_QUERY"),
        )
        return list(response.embeddings[0].values)

    if openai_client is None:
        raise RuntimeError("OpenAI 클라이언트가 생성되지 않았습니다.")

    try:
        response = openai_client.embeddings.create(
            model=openai_model,
            input=query,
        )
    except Exception as exc:
        if is_quota_error(exc):
            raise RuntimeError(
                "OpenAI 임베딩 쿼터가 부족합니다. "
                ".env에서 IEUNG_EMBEDDING_PROVIDER=local로 바꾸고 "
                "`python rag/build_chroma_index.py --reset`을 다시 실행하세요."
            ) from exc
        raise

    return response.data[0].embedding


def get_chroma_collection():
    settings = load_settings()

    openai_client = (
        OpenAI(api_key=settings["openai_api_key"])
        if settings["embedding_provider"] == "openai"
        else None
    )

    gemini_client = (
        create_gemini_client(settings["gemini_api_key"])
        if settings["embedding_provider"] == "gemini"
        else None
    )

    chroma_client = chromadb.PersistentClient(path=str(settings["persist_dir"]))
    collection = chroma_client.get_collection(name=settings["collection_name"])

    return settings, openai_client, gemini_client, collection


def search_documents(
    query: str,
    top_k: int = 5,
    where: dict | None = None,
    where_document: dict | None = None,
) -> list[dict]:
    settings, openai_client, gemini_client, collection = get_chroma_collection()

    query_embedding = embed_query(
        openai_client=openai_client,
        gemini_client=gemini_client,
        provider=settings["embedding_provider"],
        openai_model=settings["embedding_model"],
        gemini_model=settings["gemini_embedding_model"],
        query=query,
    )

    query_args = {
        "query_embeddings": [query_embedding],
        "n_results": top_k,
        "include": ["documents", "metadatas", "distances"],
    }

    if where:
        query_args["where"] = where

    if where_document:
        query_args["where_document"] = where_document

    result = collection.query(**query_args)

    docs: list[dict] = []

    ids = result.get("ids", [[]])[0]
    documents = result.get("documents", [[]])[0]
    metadatas = result.get("metadatas", [[]])[0]
    distances = result.get("distances", [[]])[0]

    for doc_id, content, metadata, distance in zip(ids, documents, metadatas, distances):
        metadata = metadata or {}

        docs.append(
            {
                "doc_id": doc_id,
                "distance": distance,
                "word": metadata.get("word", ""),
                "doc_type": metadata.get("doc_type", ""),
                "source": metadata.get("source", ""),
                "content": content or "",
                "metadata": metadata,
            }
        )

    return docs


def extract_target_word(sentence: str) -> str | None:
    """
    입력 문장 안에서 이응 서비스의 학습 대상 문화어휘를 찾습니다.
    긴 단어를 먼저 검사해서 '권선징악' 같은 단어가 잘리지 않게 합니다.
    """
    for word in sorted(CULTURE_WORDS, key=len, reverse=True):
        if word in sentence:
            return word

    return None


def normalize_text_for_key(text: str) -> str:
    return " ".join((text or "").split())


def dedupe_documents(docs: list[dict]) -> list[dict]:
    """
    같은 내용의 문서가 반복 검색되는 것을 줄입니다.
    doc_id가 달라도 source, word, doc_type, content가 같으면 중복으로 봅니다.
    """
    seen = set()
    unique_docs: list[dict] = []

    for doc in docs:
        key = (
            doc.get("word", ""),
            doc.get("doc_type", ""),
            doc.get("source", ""),
            normalize_text_for_key(doc.get("content", ""))[:300],
        )

        if key in seen:
            continue

        seen.add(key)
        unique_docs.append(doc)

    return unique_docs


def is_krdict_doc(doc: dict) -> bool:
    source = str(doc.get("source", "")).lower()
    return source in {"krdict", "korean_basic_dict", "한국어기초사전"}


def is_opendict_doc(doc: dict) -> bool:
    source = str(doc.get("source", "")).lower()
    content = str(doc.get("content", ""))

    return (
        source in {"opendict", "open_dict", "urimalsaem", "우리말샘"}
        or "우리말샘" in content
        or "개방형 한국어 지식 대사전" in content
    )


def is_dictionary_doc(doc: dict) -> bool:
    doc_type = str(doc.get("doc_type", "")).lower()
    return doc_type in {
        "word_definition",
        "dictionary_definition",
        "dictionary",
        "definition",
    }


def is_spoken_doc(doc: dict) -> bool:
    doc_type = str(doc.get("doc_type", "")).lower()
    return doc_type == "spoken_example"


def sort_by_distance(docs: list[dict]) -> list[dict]:
    return sorted(
        docs,
        key=lambda doc: float(doc.get("distance", 999999) or 999999),
    )


def take_docs(docs: list[dict], limit: int) -> list[dict]:
    return sort_by_distance(dedupe_documents(docs))[:limit]


def search_target_word_documents(target_word: str) -> list[dict]:
    """
    대상 문화어휘의 사전 정의와 용례를 가져옵니다.

    핵심:
    - word metadata가 target_word인 문서를 넉넉히 가져온 뒤
    - 한국어기초사전, 우리말샘, 기타 사전 문서를 로컬에서 분리합니다.
    - 이렇게 해야 특정 사전 하나만 검색 결과를 독점하는 현상을 줄일 수 있습니다.
    """
    docs: list[dict] = []

    # 1. metadata.word가 정확히 대상 문화어휘인 문서 검색
    try:
        docs.extend(
            search_documents(
                query=f"{target_word} 뜻 의미 품사 사전 정의 용례",
                top_k=50,
                where={"word": {"$eq": target_word}},
            )
        )
    except Exception:
        pass

    # 2. metadata.word가 누락된 문서까지 고려해서 본문에 대상어가 들어간 문서 검색
    try:
        docs.extend(
            search_documents(
                query=f"{target_word} 우리말샘 한국어기초사전 뜻풀이 용례",
                top_k=30,
                where_document={"$contains": target_word},
            )
        )
    except Exception:
        pass

    return dedupe_documents(docs)


def search_spoken_documents(sentence: str, target_word: str | None = None) -> list[dict]:
    """
    구어체 변환에 참고할 모두의 말뭉치 예문을 가져옵니다.
    대상 문화어휘가 있으면 해당 단어가 들어간 구어체 예문을 먼저 찾고,
    없거나 부족하면 일반 구어체 예문을 가져옵니다.
    """
    docs: list[dict] = []

    if target_word:
        try:
            docs.extend(
                search_documents(
                    query=f"{target_word} 자연스러운 구어체 일상 대화 예문",
                    top_k=10,
                    where={"doc_type": {"$eq": "spoken_example"}},
                    where_document={"$contains": target_word},
                )
            )
        except Exception:
            pass

    try:
        docs.extend(
            search_documents(
                query=f"일상 대화 구어체 자연스러운 말투 {sentence}",
                top_k=10,
                where={"doc_type": {"$eq": "spoken_example"}},
            )
        )
    except Exception:
        pass

    return dedupe_documents(docs)


def search_documents_balanced(query: str, top_k: int = 8) -> list[dict]:
    """
    사용자 문장에 포함된 문화어휘를 기준으로 검색 근거를 균형 있게 구성합니다.

    반환 우선순위:
    1. 한국어기초사전 정의
    2. 우리말샘 정의/용례
    3. 기타 대상 문화어휘 사전 근거
    4. 대상 문화어휘가 들어간 구어체 예문
    5. 일반 구어체 예문

    목적:
    - 단어 의미 판단은 사전 근거로 수행합니다.
    - 문장 적합성 판단은 사전 의미와 문장 구조를 함께 봅니다.
    - 구어체 변환은 모두의 말뭉치 기반 구어체 예문을 참고합니다.
    - 대상 문화어휘를 다른 단어로 바꾸지 않도록 합니다.
    """
    target_word = extract_target_word(query)

    if not target_word:
        return search_documents(
            query=f"한국어 문장 교정 구어체 변환 {query}",
            top_k=top_k,
        )

    word_docs = search_target_word_documents(target_word)
    spoken_docs = search_spoken_documents(query, target_word)

    krdict_docs = [
        doc for doc in word_docs
        if is_krdict_doc(doc) and is_dictionary_doc(doc)
    ]

    opendict_docs = [
        doc for doc in word_docs
        if is_opendict_doc(doc) and is_dictionary_doc(doc)
    ]

    other_dictionary_docs = [
        doc for doc in word_docs
        if is_dictionary_doc(doc)
        and not is_krdict_doc(doc)
        and not is_opendict_doc(doc)
    ]

    target_spoken_docs = [
        doc for doc in spoken_docs
        if is_spoken_doc(doc) and target_word in doc.get("content", "")
    ]

    general_spoken_docs = [
        doc for doc in spoken_docs
        if is_spoken_doc(doc) and target_word not in doc.get("content", "")
    ]

    balanced_docs: list[dict] = []

    balanced_docs.extend(take_docs(krdict_docs, 3))
    balanced_docs.extend(take_docs(opendict_docs, 3))
    balanced_docs.extend(take_docs(other_dictionary_docs, 2))
    balanced_docs.extend(take_docs(target_spoken_docs, 2))
    balanced_docs.extend(take_docs(general_spoken_docs, 3))

    balanced_docs = dedupe_documents(balanced_docs)

    if not balanced_docs:
        balanced_docs = search_documents(query, top_k=top_k)

    return balanced_docs[:top_k]


def print_results(results: list[dict]) -> None:
    for index, doc in enumerate(results, start=1):
        print(f"\n[{index}] doc_id={doc.get('doc_id')} distance={doc.get('distance')}")
        print(
            f"word={doc.get('word')} "
            f"doc_type={doc.get('doc_type')} "
            f"source={doc.get('source')}"
        )
        print(doc.get("content", ""))


def main() -> None:
    try:
        results = search_documents_balanced(DEFAULT_QUERY, top_k=8)
        print(f"query: {DEFAULT_QUERY}")
        print_results(results)
    except Exception as exc:
        print(f"[ERROR] RAG 검색 실패: {exc}", file=sys.stderr)
        print(
            "먼저 `python rag/build_chroma_index.py --input output/normalized/rag_documents_combined.jsonl --reset`으로 "
            "현재 provider에 맞는 ChromaDB 인덱스를 구축했는지 확인하세요.",
            file=sys.stderr,
        )
        raise


if __name__ == "__main__":
    main()