import logging
import math
import time
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from fastapi import HTTPException
from PyPDF2 import PdfReader
from sqlalchemy.orm import Session

from app.config import settings
from app.services.document_service import get_document

logger = logging.getLogger(__name__)

_model: Any | None = None
_client: Any | None = None
EMBEDDING_BATCH_SIZE = 64
QDRANT_UPSERT_BATCH_SIZE = 32
QDRANT_MAX_RETRIES = 3


def get_embedding_model() -> Any:
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer(settings.embedding_model_name)
    return _model


def get_qdrant_client() -> Any:
    global _client
    if _client is None:
        from qdrant_client import QdrantClient

        _client = QdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key,
            timeout=300,
        )
    return _client


def iter_batches(items: list[Any], batch_size: int):
    for start in range(0, len(items), batch_size):
        yield items[start : start + batch_size]


def upsert_points_with_retry(client: Any, points: list[Any]) -> None:
    for attempt in range(1, QDRANT_MAX_RETRIES + 1):
        try:
            client.upsert(
                collection_name=settings.qdrant_collection,
                points=points,
                wait=False,
            )
            return
        except Exception:
            if attempt == QDRANT_MAX_RETRIES:
                raise
            logger.warning(
                "Qdrant upsert attempt %s/%s failed; retrying",
                attempt,
                QDRANT_MAX_RETRIES,
            )
            time.sleep(attempt * 2)


def ensure_collection(vector_size: int) -> None:
    from qdrant_client.http.models import Distance, VectorParams

    client = get_qdrant_client()
    try:
        collections = client.get_collections().collections
        exists = any(item.name == settings.qdrant_collection for item in collections)
        if not exists:
            client.create_collection(
                collection_name=settings.qdrant_collection,
                vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
            )
    except Exception as exc:
        logger.exception("Qdrant collection check failed")
        raise HTTPException(status_code=503, detail="Qdrant is unavailable") from exc


def ensure_document_id_payload_index(client: Any) -> None:
    try:
        client.create_payload_index(
            collection_name=settings.qdrant_collection,
            field_name="document_id",
            field_schema="integer",
            wait=True,
        )
    except Exception as exc:
        message = str(exc).lower()
        if "already exists" not in message:
            logger.exception("Qdrant payload index creation failed")
            raise HTTPException(status_code=503, detail="Failed to prepare Qdrant index")


def delete_existing_document_points(client: Any, document_id: int) -> None:
    from qdrant_client.http.models import FieldCondition, Filter, FilterSelector, MatchValue

    try:
        ensure_document_id_payload_index(client)
        client.delete(
            collection_name=settings.qdrant_collection,
            points_selector=FilterSelector(
                filter=Filter(
                    must=[
                        FieldCondition(
                            key="document_id",
                            match=MatchValue(value=document_id),
                        )
                    ]
                )
            ),
            wait=True,
        )
    except Exception:
        logger.exception("Qdrant cleanup failed for document_id=%s", document_id)
        raise HTTPException(status_code=503, detail="Failed to clean old document chunks")


def extract_text_from_pdf(file_path: str) -> str:
    path = Path(file_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="PDF file not found")

    reader = PdfReader(str(path))
    text_parts = []
    for page in reader.pages:
        page_text = page.extract_text() or ""
        if page_text.strip():
            text_parts.append(page_text)

    text = "\n".join(text_parts).strip()
    if not text:
        raise HTTPException(status_code=400, detail="No extractable text found in PDF")
    return text


def split_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    chunks = []
    start = 0
    text = " ".join(text.split())
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start += chunk_size - overlap
    return chunks


def index_document(db: Session, document_id: int) -> int:
    from qdrant_client.http.models import PointStruct

    document = get_document(db, document_id)
    text = extract_text_from_pdf(document.file_path)
    chunks = split_text(text, chunk_size=500, overlap=50)
    if not chunks:
        raise HTTPException(status_code=400, detail="No chunks generated from document")

    model = get_embedding_model()
    client = get_qdrant_client()
    indexed_count = 0
    total_batches = math.ceil(len(chunks) / EMBEDDING_BATCH_SIZE)
    collection_ready = False

    try:
        for batch_number, chunk_batch in enumerate(
            iter_batches(chunks, EMBEDDING_BATCH_SIZE),
            start=1,
        ):
            embeddings = model.encode(
                chunk_batch,
                normalize_embeddings=True,
                show_progress_bar=False,
            ).tolist()
            if not collection_ready:
                ensure_collection(len(embeddings[0]))
                delete_existing_document_points(client, document.id)
                collection_ready = True

            points = [
                PointStruct(
                    id=str(
                        uuid5(
                            NAMESPACE_URL,
                            f"document:{document.id}:chunk:{chunk_index}",
                        )
                    ),
                    vector=embedding,
                    payload={"text": chunk, "document_id": document.id},
                )
                for chunk_index, (chunk, embedding) in enumerate(
                    zip(chunk_batch, embeddings),
                    start=(batch_number - 1) * EMBEDDING_BATCH_SIZE,
                )
            ]

            for point_batch in iter_batches(points, QDRANT_UPSERT_BATCH_SIZE):
                upsert_points_with_retry(client, point_batch)
                indexed_count += len(point_batch)

            logger.info(
                "Indexed batch %s/%s for document_id=%s",
                batch_number,
                total_batches,
                document.id,
            )
    except Exception as exc:
        logger.exception("Document indexing failed")
        raise HTTPException(status_code=503, detail="Failed to index document") from exc

    logger.info("Indexed %s chunks for document_id=%s", indexed_count, document.id)
    return indexed_count


def search_chunks(query: str) -> list[dict]:
    if not query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    model = get_embedding_model()
    query_vector = model.encode(query, normalize_embeddings=True).tolist()
    ensure_collection(len(query_vector))

    try:
        results = get_qdrant_client().search(
            collection_name=settings.qdrant_collection,
            query_vector=query_vector,
            limit=20,
            with_payload=True,
        )
    except Exception as exc:
        logger.exception("Qdrant search failed")
        raise HTTPException(status_code=503, detail="Failed to search chunks") from exc
    reranked = sorted(results, key=lambda item: item.score, reverse=True)[:5]
    return [
        {
            "text": item.payload.get("text", ""),
            "document_id": item.payload.get("document_id"),
            "score": float(item.score),
        }
        for item in reranked
    ]
