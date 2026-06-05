from __future__ import annotations

import os
import sys
from pathlib import Path

import chromadb
from dotenv import load_dotenv
from openai import OpenAI

from embedding_utils import is_quota_error, local_embedding


ROOT_DIR = Path(__file__).resolve().parents[2]
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
        response = openai_client.embeddings.create(model=openai_model, input=query)
    except Exception as exc:
        if is_quota_error(exc):
            raise RuntimeError(
                "OpenAI 임베딩 쿼터가 부족합니다. "
                ".env에서 IEUNG_EMBEDDING_PROVIDER=local로 바꾸고 "
                "`python dictionary_pipeline/retrieval/build_chroma_index.py --reset`을 다시 실행하세요."
            ) from exc
        raise

    return response.data[0].embedding


def get_chroma_collection():
    settings = load_settings()

    openai_client = OpenAI(api_key=settings["openai_api_key"]) if settings["embedding_provider"] == "openai" else None
    gemini_client = (
        create_gemini_client(settings["gemini_api_key"]) if settings["embedding_provider"] == "gemini" else None
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
        "where": {"doc_type": {"$eq": "word_definition"}},
    }

    if where:
        query_args["where"] = {"$and": [query_args["where"], where]}

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
    for word in sorted(CULTURE_WORDS, key=len, reverse=True):
        if word in sentence:
            return word
    return None


def normalize_text_for_key(text: str) -> str:
    return " ".join((text or "").split())


def dedupe_documents(docs: list[dict]) -> list[dict]:
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
    return str(doc.get("source", "")).lower() == "krdict"


def is_opendict_doc(doc: dict) -> bool:
    return str(doc.get("source", "")).lower() == "opendict"


def sort_by_distance(docs: list[dict]) -> list[dict]:
    return sorted(docs, key=lambda doc: float(doc.get("distance", 999999) or 999999))


def take_docs(docs: list[dict], limit: int) -> list[dict]:
    return sort_by_distance(dedupe_documents(docs))[:limit]


def search_target_word_documents(target_word: str) -> list[dict]:
    docs: list[dict] = []

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


def search_dictionary_documents_balanced(query: str, top_k: int = 6) -> list[dict]:
    target_word = extract_target_word(query)
    if not target_word:
        return search_documents(query=f"한국어 문장 교정 의미 판단 {query}", top_k=top_k)

    word_docs = search_target_word_documents(target_word)
    krdict_docs = [doc for doc in word_docs if is_krdict_doc(doc)]
    opendict_docs = [doc for doc in word_docs if is_opendict_doc(doc)]
    other_docs = [doc for doc in word_docs if not is_krdict_doc(doc) and not is_opendict_doc(doc)]

    balanced_docs: list[dict] = []
    balanced_docs.extend(take_docs(krdict_docs, 3))
    balanced_docs.extend(take_docs(opendict_docs, 3))
    balanced_docs.extend(take_docs(other_docs, 2))
    return dedupe_documents(balanced_docs)[:top_k]


def print_results(results: list[dict]) -> None:
    for index, doc in enumerate(results, start=1):
        print(f"\n[{index}] doc_id={doc.get('doc_id')} distance={doc.get('distance')}")
        print(f"word={doc.get('word')} doc_type={doc.get('doc_type')} source={doc.get('source')}")
        print(doc.get("content", ""))


def main() -> None:
    try:
        results = search_dictionary_documents_balanced(DEFAULT_QUERY, top_k=6)
        print(f"query: {DEFAULT_QUERY}")
        print_results(results)
    except Exception as exc:
        print(f"[ERROR] 사전 RAG 검색 실패: {exc}", file=sys.stderr)
        raise


if __name__ == "__main__":
    main()
