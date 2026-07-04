import chromadb
from ..config import settings
from ..embeddings import embed_texts

COLLECTION = "scigraph_chunks"


class VectorStore:
    def __init__(self):
        self.client = chromadb.HttpClient(host=settings.chroma_host, port=settings.chroma_port)
        self.collection = self.client.get_or_create_collection(
            name=COLLECTION, metadata={"hnsw:space": "cosine"})

    def add(self, ids, texts, metadatas):
        embeddings = embed_texts(texts, prefix="passage: ")
        self.collection.add(ids=ids, documents=texts,
                            embeddings=embeddings, metadatas=metadatas)

    def query(self, text: str, k: int = 6, where: dict | None = None):
        emb = embed_texts([text], prefix="query: ")[0]
        res = self.collection.query(query_embeddings=[emb], n_results=k, where=where)
        out = []
        for i in range(len(res["ids"][0])):
            out.append({
                "id": res["ids"][0][i],
                "text": res["documents"][0][i],
                "meta": res["metadatas"][0][i],
                "distance": res["distances"][0][i] if res.get("distances") else None,
            })
        return out

    def existing_ids(self, ids: list[str]) -> set:
        if not ids:
            return set()
        try:
            got = self.collection.get(ids=ids, include=[])
            return set(got.get("ids", []))
        except Exception:
            return set()

    def count(self):
        return self.collection.count()

    def wipe(self):
        try:
            self.client.delete_collection(COLLECTION)
        except Exception:
            pass
        self.collection = self.client.get_or_create_collection(
            name=COLLECTION, metadata={"hnsw:space": "cosine"})


vector_store = VectorStore()
