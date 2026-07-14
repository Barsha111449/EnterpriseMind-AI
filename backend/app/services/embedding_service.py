from functools import lru_cache

from sentence_transformers import SentenceTransformer


MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_DIMENSION = 384


@lru_cache(maxsize=1)
def get_embedding_model() -> SentenceTransformer:
    """Load and reuse the embedding model."""

    return SentenceTransformer(MODEL_NAME)


def generate_embeddings(
    texts: list[str],
) -> list[list[float]]:
    """Convert text strings into normalized embedding vectors."""

    if not texts:
        return []

    model = get_embedding_model()

    embeddings = model.encode(
        texts,
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=False,
    )

    if embeddings.ndim == 1:
        embeddings = embeddings.reshape(1, -1)

    if embeddings.shape[1] != EMBEDDING_DIMENSION:
        raise ValueError(
            "The embedding model returned an unexpected dimension."
        )

    return embeddings.astype("float32").tolist()