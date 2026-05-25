import json
import os
import sys
from pathlib import Path

import chromadb
from dotenv import load_dotenv
from openai import OpenAI

from embedding_utils import is_quota_error, local_embedding


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_QUERY = "나는 이 카페를 정이 들었다."


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
        raise RuntimeError("지원하지 않는 임베딩 provider입니다. IEUNG_EMBEDDING_PROVIDER 값을 openai, gemini, local 중 하나로 설정하세요.")

    try:
        response = openai_client.embeddings.create(model=openai_model, input=query)
    except Exception as exc:
        if is_quota_error(exc):
            raise RuntimeError(
                "OpenAI 임베딩 쿼터가 부족합니다. .env에서 IEUNG_EMBEDDING_PROVIDER=local로 바꾸고 "
                "`python rag/build_chroma_index.py --reset`을 다시 실행하세요."
            ) from exc
        raise
    return response.data[0].embedding


def search_documents(query: str, top_k: int = 5) -> list[dict]:
    settings = load_settings()
    openai_client = OpenAI(api_key=settings["openai_api_key"]) if settings["embedding_provider"] == "openai" else None
    gemini_client = create_gemini_client(settings["gemini_api_key"]) if settings["embedding_provider"] == "gemini" else None
    chroma_client = chromadb.PersistentClient(path=str(settings["persist_dir"]))
    collection = chroma_client.get_collection(name=settings["collection_name"])

    query_embedding = embed_query(
        openai_client=openai_client,
        gemini_client=gemini_client,
        provider=settings["embedding_provider"],
        openai_model=settings["embedding_model"],
        gemini_model=settings["gemini_embedding_model"],
        query=query,
    )
    result = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        include=["documents", "metadatas", "distances"],
    )

    docs = []
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
                "content": content,
                "metadata": metadata,
            }
        )
    return docs


def print_results(results: list[dict]) -> None:
    for index, doc in enumerate(results, start=1):
        print(f"\n[{index}] doc_id={doc['doc_id']} distance={doc['distance']}")
        print(f"word={doc['word']} doc_type={doc['doc_type']} source={doc['source']}")
        print(doc["content"])


def main() -> None:
    try:
        results = search_documents(DEFAULT_QUERY, top_k=5)
        print(f"query: {DEFAULT_QUERY}")
        print_results(results)
    except Exception as exc:
        print(f"[ERROR] RAG 검색 실패: {exc}", file=sys.stderr)
        print("먼저 `python rag/build_chroma_index.py --reset`으로 현재 provider에 맞는 ChromaDB 인덱스를 구축했는지 확인하세요.", file=sys.stderr)
        raise


if __name__ == "__main__":
    main()
