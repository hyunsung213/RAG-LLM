import argparse
import json
import os
import sys
from pathlib import Path
from typing import Iterable

import chromadb
from dotenv import load_dotenv
from openai import OpenAI

from embedding_utils import is_quota_error, local_embeddings


ROOT_DIR = Path(__file__).resolve().parents[1]
RAG_DOCS_PATH = ROOT_DIR / "output" / "normalized" / "rag_documents.jsonl"


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


def resolve_project_path(value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = ROOT_DIR / path
    return path


def read_jsonl(path: Path) -> Iterable[dict]:
    with path.open("r", encoding="utf-8-sig") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as exc:
                print(f"[WARN] JSON 파싱 실패: {path}:{line_no} - {exc}", file=sys.stderr)


def chunks(items: list[dict], batch_size: int) -> Iterable[list[dict]]:
    for start in range(0, len(items), batch_size):
        yield items[start : start + batch_size]


def metadata_for_chroma(doc: dict) -> dict:
    metadata = doc.get("metadata") or {}
    tags = metadata.get("tags", [])
    if isinstance(tags, list):
        tags = "|".join(str(tag) for tag in tags)

    # Chroma metadata는 스칼라 타입만 안정적으로 저장되므로 필요한 값만 평탄화한다.
    return {
        "doc_type": str(doc.get("doc_type", "")),
        "word": str(doc.get("word", "")),
        "source": str(metadata.get("source", "")),
        "pos": str(metadata.get("pos", "")),
        "difficulty": str(metadata.get("difficulty", "")),
        "tags": str(tags),
    }


def create_gemini_client(api_key: str):
    from google import genai

    return genai.Client(api_key=api_key)


def embed_texts(
    *,
    openai_client: OpenAI | None,
    gemini_client,
    provider: str,
    openai_model: str,
    gemini_model: str,
    texts: list[str],
    task_type: str = "RETRIEVAL_DOCUMENT",
) -> list[list[float]]:
    if provider == "local":
        return local_embeddings(texts)

    if provider == "gemini":
        from google.genai import types

        # gemini-embedding-001은 문자열 리스트에 대해 개별 임베딩을 반환한다.
        # gemini-embedding-2는 다중 입력을 하나로 집계할 수 있어 batch 처리에는 001을 기본값으로 둔다.
        response = gemini_client.models.embed_content(
            model=gemini_model,
            contents=texts,
            config=types.EmbedContentConfig(task_type=task_type),
        )
        return [list(embedding.values) for embedding in response.embeddings]

    if openai_client is None:
        raise RuntimeError("지원하지 않는 임베딩 provider입니다. IEUNG_EMBEDDING_PROVIDER 값을 openai, gemini, local 중 하나로 설정하세요.")

    try:
        response = openai_client.embeddings.create(model=openai_model, input=texts)
    except Exception as exc:
        if is_quota_error(exc):
            raise RuntimeError(
                "OpenAI 임베딩 쿼터가 부족합니다. .env에서 IEUNG_EMBEDDING_PROVIDER=local로 바꾸면 "
                "로컬 해시 임베딩으로 개발용 인덱스를 만들 수 있습니다."
            ) from exc
        raise
    return [item.embedding for item in response.data]


def get_collection(chroma_client: chromadb.PersistentClient, name: str, reset: bool):
    if reset:
        try:
            chroma_client.delete_collection(name)
            print(f"[INFO] 기존 Chroma collection 삭제: {name}")
        except Exception:
            pass
    return chroma_client.get_or_create_collection(name=name)


def existing_ids(collection, ids: list[str]) -> set[str]:
    if not ids:
        return set()
    try:
        result = collection.get(ids=ids)
        return set(result.get("ids", []))
    except Exception as exc:
        print(f"[WARN] 기존 doc_id 확인 실패. 중복 방지는 batch 내부 기준으로만 진행합니다: {exc}", file=sys.stderr)
        return set()


def build_index(rag_docs_path: Path = RAG_DOCS_PATH, batch_size: int = 50, reset: bool = False) -> dict:
    settings = load_settings()
    if not rag_docs_path.exists():
        raise FileNotFoundError(f"RAG 문서 파일이 없습니다: {rag_docs_path}")

    settings["persist_dir"].mkdir(parents=True, exist_ok=True)
    openai_client = OpenAI(api_key=settings["openai_api_key"]) if settings["embedding_provider"] == "openai" else None
    gemini_client = create_gemini_client(settings["gemini_api_key"]) if settings["embedding_provider"] == "gemini" else None
    chroma_client = chromadb.PersistentClient(path=str(settings["persist_dir"]))
    collection = get_collection(chroma_client, settings["collection_name"], reset=reset)

    docs = [doc for doc in read_jsonl(rag_docs_path) if doc.get("doc_id") and doc.get("content")]
    total_read = len(docs)
    total_added = 0
    total_skipped = 0

    for batch_index, batch in enumerate(chunks(docs, batch_size), start=1):
        ids = [str(doc["doc_id"]) for doc in batch]
        duplicate_ids = existing_ids(collection, ids)
        new_docs = [doc for doc in batch if str(doc["doc_id"]) not in duplicate_ids]
        total_skipped += len(batch) - len(new_docs)

        if not new_docs:
            print(f"[INFO] batch {batch_index}: 모두 이미 저장됨")
            continue

        documents = [str(doc["content"]) for doc in new_docs]
        embeddings = embed_texts(
            openai_client=openai_client,
            gemini_client=gemini_client,
            provider=settings["embedding_provider"],
            openai_model=settings["embedding_model"],
            gemini_model=settings["gemini_embedding_model"],
            texts=documents,
            task_type="RETRIEVAL_DOCUMENT",
        )
        metadatas = [metadata_for_chroma(doc) for doc in new_docs]
        new_ids = [str(doc["doc_id"]) for doc in new_docs]

        collection.add(ids=new_ids, documents=documents, embeddings=embeddings, metadatas=metadatas)
        total_added += len(new_docs)
        print(f"[INFO] batch {batch_index}: {len(new_docs)}건 저장")

    stats = {
        "read": total_read,
        "added": total_added,
        "skipped_existing": total_skipped,
        "collection": settings["collection_name"],
        "persist_dir": str(settings["persist_dir"]),
    }
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    print("[DONE] ChromaDB 인덱스 저장 완료")
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="rag_documents.jsonl을 ChromaDB에 저장")
    parser.add_argument("--input", type=Path, default=RAG_DOCS_PATH)
    parser.add_argument("--batch-size", type=int, default=50)
    parser.add_argument("--reset", action="store_true", help="기존 collection을 삭제하고 다시 생성합니다.")
    args = parser.parse_args()

    try:
        build_index(args.input, batch_size=args.batch_size, reset=args.reset)
    except Exception as exc:
        print(f"[ERROR] Chroma 인덱스 구축 실패: {exc}", file=sys.stderr)
        raise


if __name__ == "__main__":
    main()
