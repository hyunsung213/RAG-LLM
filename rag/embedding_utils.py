import hashlib
import math
import re


LOCAL_EMBEDDING_DIM = 384


def tokenize_for_local_embedding(text: str) -> list[str]:
    """API 쿼터가 없을 때 로컬 테스트용으로 쓰는 간단한 문자 n-gram 토크나이저."""
    text = (text or "").lower()
    chunks = re.findall(r"[가-힣a-z0-9]+", text)
    tokens: list[str] = []
    for chunk in chunks:
        tokens.append(chunk)
        if len(chunk) >= 2:
            tokens.extend(chunk[i : i + 2] for i in range(len(chunk) - 1))
        if len(chunk) >= 3:
            tokens.extend(chunk[i : i + 3] for i in range(len(chunk) - 2))
    return tokens


def local_embedding(text: str, dim: int = LOCAL_EMBEDDING_DIM) -> list[float]:
    """결정적 해시 기반 임베딩. 품질은 낮지만 OpenAI 쿼터 없이 Chroma 흐름을 검증할 수 있다."""
    vector = [0.0] * dim
    for token in tokenize_for_local_embedding(text):
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % dim
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vector[index] += sign

    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        return vector
    return [value / norm for value in vector]


def local_embeddings(texts: list[str]) -> list[list[float]]:
    return [local_embedding(text) for text in texts]


def is_quota_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return "insufficient_quota" in text or "exceeded your current quota" in text
