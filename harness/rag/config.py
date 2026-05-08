from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class RagConfig:
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str | None = None
    collection_name: str = "internal_kb"
    knowledge_dir: Path = Path("docs/knowledge")
    embedding_model: str = "BAAI/bge-small-zh-v1.5"
    top_k: int = 5
    chunk_size: int = 800
    chunk_overlap: int = 120


def load_rag_config(project_root: Path) -> RagConfig:
    knowledge_dir = os.getenv("RAG_KB_DIR", "docs/knowledge").strip() or "docs/knowledge"
    return RagConfig(
        qdrant_url=os.getenv("QDRANT_URL", "http://localhost:6333").strip() or "http://localhost:6333",
        qdrant_api_key=os.getenv("QDRANT_API_KEY", "").strip() or None,
        collection_name=os.getenv("RAG_COLLECTION_NAME", "internal_kb").strip() or "internal_kb",
        knowledge_dir=(project_root / knowledge_dir).resolve(),
        embedding_model=os.getenv("RAG_EMBEDDING_MODEL", "BAAI/bge-small-zh-v1.5").strip()
        or "BAAI/bge-small-zh-v1.5",
        top_k=max(1, int(os.getenv("RAG_TOP_K", "5"))),
        chunk_size=max(200, int(os.getenv("RAG_CHUNK_SIZE", "800"))),
        chunk_overlap=max(0, int(os.getenv("RAG_CHUNK_OVERLAP", "120"))),
    )
