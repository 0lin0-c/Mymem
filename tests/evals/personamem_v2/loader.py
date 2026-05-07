from __future__ import annotations

import json
import logging
import os
import re
from ast import literal_eval
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

from tests.evals.personamem_v2.models import PersonaMemQuestion, PersonaMemSample

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).parents[3]
DATA_ROOT = REPO_ROOT / "data"
PERSONAMEM_DATA_DIR = DATA_ROOT / "personamem_v2"
PERSONAMEM_CACHE_DIR = DATA_ROOT / "personamem_v2_hf_cache"
DEFAULT_CONFIG_NAME = "benchmark"
DEFAULT_SPLIT = "benchmark_text"
SPLIT_FILES = {
    "benchmark_text": "benchmark/text/benchmark.csv",
    "train_text": "benchmark/text/train.csv",
    "val_text": "benchmark/text/val.csv",
}


def load_personamem_rows(
    split: str = DEFAULT_SPLIT,
    max_rows: int | None = None,
    cache_dir: Path = PERSONAMEM_CACHE_DIR,
) -> list[dict[str, Any]]:
    """Load PersonaMem-v2 rows from Hugging Face with project-local cache."""
    filename = SPLIT_FILES.get(split)
    if not filename:
        raise ValueError(
            f"Unsupported PersonaMem-v2 split for text-only harness: {split}. "
            f"Expected one of {sorted(SPLIT_FILES)}."
        )
    _configure_project_hf_cache(cache_dir)
    try:
        from huggingface_hub import hf_hub_download
        from datasets import load_dataset
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Missing dependency 'datasets' or 'huggingface_hub'. Install project requirements or run: "
            "conda run -n memory_agent pip install datasets huggingface_hub"
        ) from exc

    cache_dir.mkdir(parents=True, exist_ok=True)
    csv_path = hf_hub_download(
        repo_id="bowen-upenn/PersonaMem-v2",
        repo_type="dataset",
        filename=filename,
        cache_dir=str(cache_dir / "hub"),
        local_dir=str(cache_dir / "raw"),
    )
    dataset = load_dataset(
        "csv",
        data_files=str(csv_path),
        split="train",
        cache_dir=str(cache_dir / "datasets"),
    )
    if max_rows is not None:
        dataset = dataset.select(range(min(max_rows, len(dataset))))
    return [dict(row) for row in dataset]


def _configure_project_hf_cache(cache_dir: Path) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("HF_HOME", str(cache_dir / "home"))
    os.environ.setdefault("HF_HUB_CACHE", str(cache_dir / "hub"))
    os.environ.setdefault("HF_DATASETS_CACHE", str(cache_dir / "datasets"))
    os.environ.setdefault("HF_XET_CACHE", str(cache_dir / "xet"))


def save_rows_snapshot(
    rows: list[dict[str, Any]],
    split: str,
    output_dir: Path = PERSONAMEM_DATA_DIR,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{split}_rows.json"
    path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def build_samples(
    rows: Iterable[dict[str, Any]],
    split: str,
    max_personas: int | None = None,
    max_questions: int | None = None,
    persona_id: str | None = None,
) -> list[PersonaMemSample]:
    grouped: dict[str, list[PersonaMemQuestion]] = defaultdict(list)
    persona_metadata: dict[str, dict[str, Any]] = {}
    persona_order: list[str] = []
    target_persona_id = str(persona_id).strip() if persona_id is not None else None

    for row_index, row in enumerate(rows):
        question = _pick(row, "user_query", "query", "question")
        answer = _pick(row, "correct_answer", "answer", "gold_answer")
        row_persona_id = str(_pick(row, "persona_id", "persona", default="unknown")).strip()
        if not question or not answer or not row_persona_id:
            logger.debug("Skipping incomplete PersonaMem row %s: keys=%s", row_index, sorted(row))
            continue
        if target_persona_id is not None and row_persona_id != target_persona_id:
            continue

        if row_persona_id not in grouped:
            if max_personas is not None and len(persona_order) >= max_personas:
                continue
            persona_order.append(row_persona_id)
            persona_metadata[row_persona_id] = _extract_persona_metadata(row)

        if max_questions is not None and len(grouped[row_persona_id]) >= max_questions:
            continue

        snippet = _pick(row, "related_conversation_snippet", "conversation_snippet", default="")
        preference = _pick(row, "preference", "supporting_preference", default="")
        evidence = [text for text in [snippet, preference] if text]
        incorrect_answers = _coerce_list(_pick(row, "incorrect_answers", "negative_answers", default=[]))
        grouped[row_persona_id].append(
            PersonaMemQuestion(
                persona_id=row_persona_id,
                question=str(question),
                answer=str(answer),
                incorrect_answers=[str(item) for item in incorrect_answers],
                evidence=[str(item) for item in evidence],
                preference=str(preference or ""),
                related_conversation_snippet=str(snippet or ""),
                pref_type=str(_pick(row, "pref_type", "preference_type", default="")),
                who=str(_pick(row, "who", default="")),
                updated=str(_pick(row, "updated", default="")),
                source_split=split,
                row_index=row_index,
            )
        )

    return [
        PersonaMemSample(
            persona_id=persona_id,
            user_key=f"personamem_v2_persona_{persona_id}",
            short_persona=str(persona_metadata.get(persona_id, {}).get("short_persona", "")),
            expanded_persona=str(persona_metadata.get(persona_id, {}).get("expanded_persona", "")),
            interests=list(persona_metadata.get(persona_id, {}).get("interests", [])),
            questions=grouped[persona_id],
        )
        for persona_id in persona_order
        if grouped[persona_id]
    ]


def _extract_persona_metadata(row: dict[str, Any]) -> dict[str, Any]:
    short_persona = str(_pick(row, "short_persona", default="") or "")
    expanded_persona = str(_pick(row, "expanded_persona", default="") or "")
    return {
        "short_persona": short_persona,
        "expanded_persona": expanded_persona,
        "interests": _extract_interests_from_persona(expanded_persona, short_persona),
    }


def _extract_interests_from_persona(expanded_persona: str, short_persona: str = "") -> list[str]:
    """Extract stable interest tags for onboarding from PersonaMem persona text."""
    candidates: list[str] = []
    parsed = _loads_json_like(expanded_persona)
    if isinstance(parsed, dict):
        for key in ("hobbies_interests", "interests", "hobbies"):
            value = parsed.get(key)
            if isinstance(value, list):
                candidates.extend(str(item) for item in value)
            elif isinstance(value, str):
                candidates.append(value)

        for section_name in ("personality", "occupation", "education"):
            section = parsed.get(section_name)
            if isinstance(section, dict):
                for value in section.values():
                    if isinstance(value, str) and 2 <= len(value) <= 80:
                        candidates.append(value)

    if not candidates and short_persona:
        short_parsed = _loads_json_like(short_persona)
        if isinstance(short_parsed, dict) and short_parsed.get("persona"):
            candidates.append(str(short_parsed["persona"]))
        else:
            candidates.extend(re.findall(r"[A-Za-z][A-Za-z][A-Za-z \-]{2,60}", short_persona))

    cleaned: list[str] = []
    seen = set()
    for item in candidates:
        text = re.sub(r"\s+", " ", str(item)).strip(" .;:,-")
        if not text or text.lower() in {"persona", "short persona"} or len(text) > 160:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(text)
        if len(cleaned) >= 8:
            break
    return cleaned


def _loads_json_like(value: str) -> Any:
    if not value:
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        pass
    try:
        return literal_eval(value)
    except (ValueError, SyntaxError):
        return None


def snippet_to_turns(question: PersonaMemQuestion) -> list[tuple[str, str]]:
    """Convert a PersonaMem snippet into user/assistant pairs for MemoryWriter."""
    snippet = (question.related_conversation_snippet or question.preference or "").strip()
    if not snippet:
        return []

    parsed = _parse_message_list(snippet)
    if parsed:
        return _pair_turns(parsed)

    return [
        (
            f"Preference evidence for persona {question.persona_id}: {snippet}",
            "I will remember this preference for future personalized answers.",
        )
    ]


def _parse_message_list(raw: str) -> list[tuple[str, str]]:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return []

    messages: list[tuple[str, str]] = []
    if isinstance(value, list):
        for item in value:
            if isinstance(item, dict):
                role = str(item.get("role") or item.get("speaker") or "").lower()
                content = str(item.get("content") or item.get("text") or "").strip()
                if content:
                    messages.append((role or "user", content))
            elif isinstance(item, str) and item.strip():
                messages.append(("user", item.strip()))
    return messages


def _pair_turns(messages: list[tuple[str, str]]) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    pending_user: str | None = None
    for role, content in messages:
        normalized_role = role.lower()
        if normalized_role in {"user", "human", "customer"}:
            pending_user = content
        elif pending_user:
            pairs.append((pending_user, content))
            pending_user = None
    if pending_user:
        pairs.append((pending_user, "Acknowledged. I will keep this in mind."))
    return pairs


def _pick(row: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return value
    return default


def _coerce_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return []
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError:
            return [stripped]
        return parsed if isinstance(parsed, list) else [parsed]
    return [value]
