class VectorStore:
    def add(self, documents, embeddings=None, metadata=None):
        raise NotImplementedError
    def search(self, query, top_k=6, filters=None):
        raise NotImplementedError
