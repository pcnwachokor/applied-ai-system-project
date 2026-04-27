import os
import json
import logging
import numpy as np

logger = logging.getLogger(__name__)

DOCS_PATH = os.path.join(os.path.dirname(__file__), "docs", "narrative_templates.json")
MIN_SCORE = 0.4

_model = None
_archetype_index = None
_archetype_chunks = None
_genre_map = None


def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


def _ensure_index():
    global _archetype_index, _archetype_chunks, _genre_map
    if _archetype_index is not None:
        return

    import faiss

    with open(DOCS_PATH) as f:
        templates = json.load(f)

    model = _get_model()

    archetypes = [t for t in templates if t["type"] == "archetype"]
    genres = [t for t in templates if t["type"] == "genre"]

    _archetype_chunks = archetypes
    texts = [t["text"] for t in archetypes]
    embeddings = model.encode(texts, convert_to_numpy=True)
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    embeddings = (embeddings / norms).astype(np.float32)

    dim = embeddings.shape[1]
    _archetype_index = faiss.IndexFlatIP(dim)
    _archetype_index.add(embeddings)

    _genre_map = {}
    for g in genres:
        key = g["genre"].lower()
        _genre_map.setdefault(key, []).append(g["text"])

    logger.info(
        "[rag_engine] index built: %d archetype chunks, %d genre entries",
        len(archetypes),
        len(genres),
    )


def retrieve_archetypes(query: str, k: int = 2) -> list[dict]:
    """Return top-k archetype chunks for query with similarity scores."""
    _ensure_index()
    model = _get_model()

    vec = model.encode([query], convert_to_numpy=True)
    vec = (vec / np.linalg.norm(vec)).astype(np.float32)

    scores, indices = _archetype_index.search(vec, k)

    results = []
    for score, idx in zip(scores[0], indices[0]):
        chunk = _archetype_chunks[idx]
        results.append({"text": chunk["text"], "id": chunk["id"], "score": float(score)})
        logger.info("[rag_engine] retrieved id=%s score=%.2f", chunk["id"], score)

    return results


def retrieve_genre(genre: str) -> list[str]:
    """Return genre flavor text chunks for the selected genre."""
    _ensure_index()
    key = genre.lower()
    chunks = _genre_map.get(key) or _genre_map.get("neutral", [])
    logger.info("[rag_engine] genre=%s, %d chunks", key, len(chunks))
    return chunks


def reset_index():
    """Clear cached index — used in tests to force a fresh build."""
    global _archetype_index, _archetype_chunks, _genre_map, _model
    _archetype_index = None
    _archetype_chunks = None
    _genre_map = None
    _model = None
