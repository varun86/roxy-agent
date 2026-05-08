from __future__ import annotations

from qdrant_client import QdrantClient

from harness.rag.chunker import DocumentChunk
from harness.rag.store import QdrantVectorStore


def test_qdrant_vector_store_upsert_and_search():
    client = QdrantClient(":memory:")
    store = QdrantVectorStore(client, "internal_kb_test")
    chunks = [
        DocumentChunk(chunk_id="a", source_path="faq/a.txt", title="A", text="退款政策说明"),
        DocumentChunk(chunk_id="b", source_path="faq/b.txt", title="B", text="发货时效说明"),
    ]
    vectors = [[1.0, 0.0], [0.0, 1.0]]

    upserted = store.upsert(chunks, vectors)
    results = store.search([0.98, 0.02], limit=1)

    assert upserted == 2
    assert len(results) == 1
    assert results[0].chunk.chunk_id == "a"
