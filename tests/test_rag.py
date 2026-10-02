from rag.chunking import chunk_text
from rag.retriever import retrieve

def test_chunking():
    assert len(chunk_text("a" * 2000, 500, 50)) > 1

def test_retrieval():
    assert retrieve("smartphone battery", "Smartphone")
