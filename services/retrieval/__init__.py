__all__ = [
    "RetrievalStrategy",
    "VectorStrategy",
    "MemoryRetriever",
]


def __getattr__(name):
    if name == "RetrievalStrategy":
        from services.retrieval.base import RetrievalStrategy
        return RetrievalStrategy
    if name == "VectorStrategy":
        from services.retrieval.vector_strategy import VectorStrategy
        return VectorStrategy
    if name == "MemoryRetriever":
        from services.retrieval.retriever import MemoryRetriever
        return MemoryRetriever
    raise AttributeError(f"module 'services.retrieval' has no attribute {name!r}")
