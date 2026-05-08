from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from qdrant_client import QdrantClient
from qdrant_client.http import models

from harness.rag.chunker import DocumentChunk


@dataclass(slots=True)
class SearchResult:
    chunk: DocumentChunk
    score: float


class QdrantVectorStore:
    def __init__(self, client: QdrantClient, collection_name: str) -> None:
        self.client = client
        self.collection_name = collection_name

    def ensure_collection(self, vector_size: int) -> None:
        collections = self.client.get_collections().collections
        existing = {item.name for item in collections}
        if self.collection_name in existing:
            return
        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=models.VectorParams(size=vector_size, distance=models.Distance.COSINE),
        )

    def upsert(self, chunks: list[DocumentChunk], vectors: list[list[float]]) -> int:
        if not chunks:
            return 0
        if len(chunks) != len(vectors):
            raise ValueError("Chunk count must match vector count.")

        self.ensure_collection(len(vectors[0]))
        timestamp = datetime.now(UTC).isoformat()
        points = [
            models.PointStruct(
                id=str(uuid5(NAMESPACE_URL, chunk.chunk_id)),
                vector=vector,
                payload={
                    "chunk_id": chunk.chunk_id,
                    "source_path": chunk.source_path,
                    "title": chunk.title,
                    "text": chunk.text,
                    "updated_at": timestamp,
                },
            )
            for chunk, vector in zip(chunks, vectors, strict=True)
        ]
        self.client.upsert(collection_name=self.collection_name, points=points, wait=True)
        return len(points)

    def search(self, query_vector: list[float], *, limit: int) -> list[SearchResult]:
        response = self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            limit=limit,
            with_payload=True,
        )
        results: list[SearchResult] = []
        for item in response.points:
            payload: dict[str, Any] = item.payload or {}
            results.append(
                SearchResult(
                    chunk=DocumentChunk(
                        chunk_id=str(payload.get("chunk_id", "")),
                        source_path=str(payload.get("source_path", "")),
                        title=str(payload.get("title", "")),
                        text=str(payload.get("text", "")),
                    ),
                    score=float(item.score),
                )
            )
        return results
