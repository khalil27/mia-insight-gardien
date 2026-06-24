"""
Accès en lecture seule à la base vectorielle ChromaDB pré-construite.
La collection est initialisée une seule fois (lazy singleton).
"""
from pathlib import Path
from typing import Any, Dict, List, Optional

# backend/chroma_db/  (3 niveaux au-dessus de ce fichier)
_CHROMA_DIR    = Path(__file__).parent.parent.parent / "chroma_db"
_COLLECTION_NAME = "mia_research"

_collection: Optional[Any] = None


def _get_collection() -> Optional[Any]:
    global _collection
    if _collection is not None:
        return _collection

    if not _CHROMA_DIR.exists():
        return None

    try:
        import chromadb
        from chromadb.utils.embedding_functions import DefaultEmbeddingFunction

        client = chromadb.PersistentClient(path=str(_CHROMA_DIR))
        ef = DefaultEmbeddingFunction()
        _collection = client.get_collection(
            name=_COLLECTION_NAME,
            embedding_function=ef,
        )
        return _collection
    except Exception:
        return None


def search(query: str, n_results: int = 4) -> List[Dict[str, str]]:
    """Recherche sémantique dans les papers.
    Retourne une liste de dicts {text, source} ou [] si RAG indisponible.
    """
    collection = _get_collection()
    if collection is None:
        return []

    try:
        results = collection.query(
            query_texts=[query],
            n_results=n_results,
            include=["documents", "metadatas"],
        )
        chunks = []
        for doc, meta in zip(results["documents"][0], results["metadatas"][0]):
            chunks.append({
                "text":   doc,
                "source": meta.get("source", ""),
            })
        return chunks
    except Exception:
        return []


def is_available() -> bool:
    return _get_collection() is not None
