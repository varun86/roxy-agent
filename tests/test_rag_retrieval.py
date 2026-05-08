from __future__ import annotations

from pathlib import Path

from qdrant_client import QdrantClient

from harness.rag.config import RagConfig
from harness.rag.service import KnowledgeBaseService


class FakeEmbedder:
    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            lowered = text.lower()
            refund_score = 1.0 if ("退款" in text or "refund" in lowered) else 0.0
            shipping_score = 1.0 if ("发货" in text or "shipping" in lowered) else 0.0
            vectors.append([refund_score, shipping_score])
        return vectors


def test_knowledge_base_service_returns_expected_chunk(tmp_path: Path):
    knowledge_dir = tmp_path / "knowledge"
    knowledge_dir.mkdir()
    (knowledge_dir / "refund.md").write_text("# 退款政策\n用户在 7 天内可以申请退款。", encoding="utf-8")
    (knowledge_dir / "shipping.txt").write_text("发货时效为 48 小时内出库。", encoding="utf-8")

    config = RagConfig(
        qdrant_url=":memory:",
        collection_name="kb_test",
        knowledge_dir=knowledge_dir,
        embedding_model="fake",
        chunk_size=200,
        chunk_overlap=20,
    )
    service = KnowledgeBaseService(
        config,
        embedder=FakeEmbedder(),
        client=QdrantClient(":memory:"),
    )

    indexed = service.index_documents()
    results = service.search("退款多久到账", top_k=1)

    assert indexed == 2
    assert len(results) == 1
    assert results[0].chunk.source_path == "refund.md"
    assert "退款" in results[0].chunk.text
