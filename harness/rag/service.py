from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from qdrant_client import QdrantClient

from harness.rag.chunker import DocumentChunk, chunk_document
from harness.rag.config import RagConfig
from harness.rag.loader import load_documents
from harness.rag.store import QdrantVectorStore, SearchResult


class Embedder(Protocol):
    def embed(self, texts: Sequence[str]) -> list[list[float]]: ...


class FastEmbedder:
    def __init__(self, model_name: str) -> None:
        self._model_name = model_name
        self._model = None

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        if self._model is None:
            from fastembed import TextEmbedding

            self._model = TextEmbedding(model_name=self._model_name)
        return [list(vector) for vector in self._model.embed(list(texts))]


class KnowledgeBaseService:
    def __init__(
        self,
        config: RagConfig,
        *,
        embedder: Embedder | None = None,
        client: QdrantClient | None = None,
        store: QdrantVectorStore | None = None,
    ) -> None:
        self.config = config
        self.embedder = embedder or FastEmbedder(config.embedding_model)
        qdrant_client = client or QdrantClient(url=config.qdrant_url, api_key=config.qdrant_api_key)
        self.store = store or QdrantVectorStore(qdrant_client, config.collection_name)

    def build_chunks(self) -> list[DocumentChunk]:
        documents = load_documents(self.config.knowledge_dir)
        chunks: list[DocumentChunk] = []
        for document in documents:
            chunks.extend(
                chunk_document(
                    document,
                    chunk_size=self.config.chunk_size,
                    chunk_overlap=self.config.chunk_overlap,
                )
            )
        return chunks

    def index_documents(self) -> int:
        chunks = self.build_chunks()
        if not chunks:
            return 0
        vectors = self.embedder.embed([chunk.text for chunk in chunks])
        return self.store.upsert(chunks, vectors)

    def search(self, query: str, *, top_k: int | None = None) -> list[SearchResult]:
        cleaned = query.strip()
        if not cleaned:
            return []
        query_vector = self.embedder.embed([cleaned])[0]
        return self.store.search(query_vector, limit=top_k or self.config.top_k)

    def render_search_results(self, query: str, *, top_k: int | None = None) -> str:
        results = self.search(query, top_k=top_k)
        if not results:
            return "No knowledge base matches found."

        lines = [f"Knowledge base results for: {query}"]
        for index, item in enumerate(results, start=1):
            snippet = item.chunk.text.replace("\n", " ").strip()
            lines.append(
                f"{index}. title={item.chunk.title} source={item.chunk.source_path} score={item.score:.4f} text={snippet}"
            )
        return "\n".join(lines)
