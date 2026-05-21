from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from tests.evals.converted_data.runner import RetrievalLayerInfo


class EvalMode(str, Enum):
    STORAGE = "storage_eval"
    RETRIEVAL = "retrieval_eval"
    ASSISTANT = "assistant_eval"


@dataclass
class PersonaMemQuestion:
    persona_id: str
    question: str
    answer: str
    incorrect_answers: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    preference: str = ""
    related_conversation_snippet: str = ""
    pref_type: str = ""
    who: str = ""
    updated: str = ""
    source_split: str = ""
    row_index: int = 0


@dataclass
class PersonaMemSample:
    persona_id: str
    user_key: str
    short_persona: str = ""
    expanded_persona: str = ""
    interests: list[str] = field(default_factory=list)
    questions: list[PersonaMemQuestion] = field(default_factory=list)

    @property
    def total_questions(self) -> int:
        return len(self.questions)


@dataclass
class PersonaMemResult:
    question: str
    expected_answer: str
    persona_id: str
    eval_mode: str = EvalMode.ASSISTANT.value
    category: int = 0
    evidence: list[str] = field(default_factory=list)
    incorrect_answers: list[str] = field(default_factory=list)
    preference: str = ""
    related_conversation_snippet: str = ""
    pref_type: str = ""
    who: str = ""
    updated: str = ""
    source_split: str = ""
    row_index: int = 0
    retrieved_contexts: list[str] = field(default_factory=list)
    retrieved_scores: list[float] = field(default_factory=list)
    retrieval_layer: RetrievalLayerInfo = field(default_factory=RetrievalLayerInfo)
    storage_hit: bool | None = None
    retrieval_hit: bool | None = None
    rank_position: int | None = None
    evaluation_trace: dict[str, Any] = field(default_factory=dict)
    llm_answer: str | None = None
    is_correct: bool | None = None
    correctness_explanation: str | None = None
    db_diagnosis: dict[str, Any] | None = None
    error: str | None = None


@dataclass
class PersonaMemReport:
    sample_index: int
    character: str
    user_id: str
    db_snapshot_id: str | None
    total_sessions: int
    total_memories: int
    total_questions: int
    results: list[PersonaMemResult] = field(default_factory=list)
    chat_model: str | None = None
    evaluator_model: str | None = None
    evaluator_isolated: bool = False
