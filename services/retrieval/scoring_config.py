from dataclasses import dataclass


@dataclass(frozen=True)
class RetrievalScoringConfig:
    recency_decay_days: int = 60
    similarity_power: float = 2.0
    access_power: float = 1.0
    recency_power: float = 0.5
    importance_power: float = 1.0

    def sql_params(self) -> dict[str, float | int]:
        return {
            "recency_decay_days": self.recency_decay_days,
            "similarity_power": self.similarity_power,
            "access_power": self.access_power,
            "recency_power": self.recency_power,
            "importance_power": self.importance_power,
        }


DEFAULT_RETRIEVAL_SCORING_CONFIG = RetrievalScoringConfig()
