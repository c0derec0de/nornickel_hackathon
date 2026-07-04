"""Мультиязычные эмбеддинги (RU/EN) через fastembed (ONNX, без torch — лёгкий и быстрый)."""
from functools import lru_cache
from .config import settings


@lru_cache(maxsize=1)
def _model():
    from fastembed import TextEmbedding
    return TextEmbedding(model_name=settings.embed_model)


def embed_texts(texts: list[str], prefix: str = "") -> list[list[float]]:
    # e5-модели требуют префиксы 'query: ' / 'passage: '
    inputs = [f"{prefix}{t}" for t in texts]
    return [vec.tolist() for vec in _model().embed(inputs)]
