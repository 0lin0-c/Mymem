from __future__ import annotations

import copy
import subprocess
import sys
from datetime import datetime
from typing import Any

from core.config import settings
from services.retrieval.scoring_config import DEFAULT_RETRIEVAL_SCORING_CONFIG


RESULT_SCHEMA_VERSION = "memory_eval_p0_2026_05"


def default_scoring_config_payload() -> dict[str, float | int]:
    return dict(DEFAULT_RETRIEVAL_SCORING_CONFIG.sql_params())


def build_run_manifest(
    *,
    harness: str,
    eval_mode: str | None,
    dataset: str | None = None,
    split: str | None = None,
    persona_id: str | None = None,
    sample: str | int | None = None,
    question_count: int | None = None,
    import_only: bool | None = None,
    retrieval_only: bool | None = None,
    reset_memory: bool | None = None,
    chat_model: str | None = None,
    evaluator_model: str | None = None,
    evaluator_isolated: bool | None = None,
    embedding_model: str | None = None,
    top_k: int | None = None,
    scoring_config: dict[str, Any] | None = None,
    rerank_config: dict[str, Any] | None = None,
    command: str | None = None,
    git_sha: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    manifest = {
        "run_id": f"{harness}_{eval_mode or 'unknown'}_{timestamp}",
        "harness": harness,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "git_sha": git_sha if git_sha is not None else _safe_git_sha(),
        "command": command if command is not None else _command_string(),
        "dataset": dataset,
        "split": split,
        "persona_id": persona_id,
        "sample": sample,
        "question_count": question_count,
        "eval_mode": eval_mode,
        "import_only": import_only,
        "retrieval_only": retrieval_only,
        "reset_memory": reset_memory,
        "chat_model": chat_model,
        "evaluator_model": evaluator_model,
        "evaluator_isolated": evaluator_isolated,
        "embedding_model": embedding_model if embedding_model is not None else settings.embedding_model,
        "top_k": top_k,
        "scoring_config": copy.deepcopy(scoring_config),
        "rerank_config": copy.deepcopy(rerank_config),
        "result_schema_version": RESULT_SCHEMA_VERSION,
    }
    if extra:
        manifest.update(extra)
    return manifest


def _safe_git_sha() -> str | None:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except Exception:
        return None
    sha = completed.stdout.strip()
    return sha or None


def _command_string() -> str | None:
    if not sys.argv:
        return None
    return " ".join(sys.argv)
