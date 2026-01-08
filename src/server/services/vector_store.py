from __future__ import annotations

from qdrant_client import QdrantClient
from qdrant_client.http import models as qdrant_models
from langchain_openai import OpenAIEmbeddings

from server.config import (
    get_openai_api_key,
    get_openai_embedding_model,
    get_openai_max_retries,
    get_openai_proxy_url,
    get_openai_timeout_seconds,
    get_qdrant_api_key,
    get_qdrant_collection,
    get_qdrant_url,
)


def _get_embeddings() -> OpenAIEmbeddings:
    api_key = get_openai_api_key()
    if not api_key or api_key == "YOUR_OPENAI_API_KEY":
        raise ValueError("Missing OpenAI API key for embeddings")
    return OpenAIEmbeddings(
        model=get_openai_embedding_model(),
        api_key=api_key,
        base_url=get_openai_proxy_url(),
        max_retries=get_openai_max_retries(),
        timeout=get_openai_timeout_seconds(),
    )


def _get_qdrant_client() -> QdrantClient:
    return QdrantClient(
        url=get_qdrant_url(),
        api_key=get_qdrant_api_key(),
        check_compatibility=False,
    )


def _ensure_collection(client: QdrantClient, collection_name: str, vector_size: int) -> None:
    try:
        info = client.get_collection(collection_name)
    except Exception:
        info = None

    if info is None:
        client.create_collection(
            collection_name=collection_name,
            vectors_config=qdrant_models.VectorParams(
                size=vector_size, distance=qdrant_models.Distance.COSINE
            ),
        )
        return

    existing_size = info.config.params.vectors.size
    if existing_size != vector_size:
        raise ValueError(
            f"Qdrant collection '{collection_name}' has vector size {existing_size}, "
            f"expected {vector_size}"
        )


def upsert_transcript_vector(
    *,
    transcript_id: int,
    file_key: str,
    text: str,
    segments: list[dict[str, object]] | None,
    diarized: bool,
) -> None:
    cleaned_text = text.strip()
    if not cleaned_text:
        return

    embeddings = _get_embeddings()
    vector = embeddings.embed_query(cleaned_text)

    collection_name = get_qdrant_collection()
    client = _get_qdrant_client()
    _ensure_collection(client, collection_name, len(vector))

    payload = {
        "file_key": file_key,
        "text": cleaned_text,
        "segment_count": len(segments) if segments else 0,
        "diarized": diarized,
    }
    point = qdrant_models.PointStruct(
        id=transcript_id,
        vector=vector,
        payload=payload,
    )
    client.upsert(collection_name=collection_name, points=[point])
