from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
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
    db_snapshot_id: str | None = None,
    dataset_hash: str | None = None,
    result_file_path: str | None = None,
    temperature: float | int | None = None,
    cache_hash: str | None = None,
    started_at: str | None = None,
    finished_at: str | None = None,
    duration_seconds: float | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    now = utc_now_iso()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    manifest = {
        "run_id": f"{harness}_{eval_mode or 'unknown'}_{timestamp}",
        "harness": harness,
        "created_at": now,
        "started_at": started_at or now,
        "finished_at": finished_at,
        "duration_seconds": duration_seconds,
        "git_sha": git_sha if git_sha is not None else _safe_git_sha(),
        "command": command if command is not None else _command_string(),
        "db_snapshot_id": db_snapshot_id,
        "dataset_hash": dataset_hash,
        "result_file_path": result_file_path,
        "temperature": temperature,
        "cache_hash": cache_hash,
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


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def finalize_run_manifest(
    manifest: dict[str, Any],
    *,
    result_file_path: str | Path | None = None,
    finished_at: str | None = None,
) -> dict[str, Any]:
    manifest["finished_at"] = finished_at or utc_now_iso()
    if result_file_path is not None:
        manifest["result_file_path"] = str(result_file_path)
    manifest["duration_seconds"] = _duration_seconds(
        manifest.get("started_at"),
        manifest.get("finished_at"),
    )
    return manifest


def stable_payload_hash(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def stable_file_hash(path: str | Path) -> str | None:
    resolved = Path(path)
    if not resolved.exists() or not resolved.is_file():
        return None
    digest = hashlib.sha256()
    with resolved.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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


def _duration_seconds(started_at: Any, finished_at: Any) -> float | None:
    if not started_at or not finished_at:
        return None
    try:
        started = datetime.fromisoformat(str(started_at).replace("Z", "+00:00"))
        finished = datetime.fromisoformat(str(finished_at).replace("Z", "+00:00"))
    except ValueError:
        return None
    elapsed = (finished - started).total_seconds()
    if elapsed < 0:
        return None
    return max(round(elapsed, 3), 0.001)


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
