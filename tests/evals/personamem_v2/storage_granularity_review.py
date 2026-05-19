"""Storage granularity review helper for PersonaMem-v2 model comparisons.

This is a read-only analysis utility. It exports per-model DB snapshots and a
lightweight row-level alignment so manual review can judge whether each model
used the right memory granularity.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import select

from core.database import AsyncSessionLocal
from tables.category import Category
from tables.resource import Resource
from tables.resource_category import ResourceCategory
from tables.user import User


MODELS: dict[str, dict[str, str]] = {
    "GLM-5.1": {
        "username": "GLM-5.1-persona66",
        "user_id": "fc20e640-320d-4ef3-a06a-4f9d5e1913e4",
        "result_json": "test_results/personamem_v2/personamem_v2_assistant_eval_results_20260508_162544.json",
    },
    "DeepSeek-V4-Pro": {
        "username": "DeepSeek-V4-Pro-persona66",
        "user_id": "c54634b7-bf63-4da9-a2c4-aaf2261545a9",
        "result_json": "test_results/personamem_v2/personamem_v2_assistant_eval_results_20260508_230326.json",
    },
    "Qwen3.5-Plus": {
        "username": "Qwen3.5-Plus-persona66",
        "user_id": "624da605-a9e3-4832-ae8c-f883f59a62a7",
        "result_json": "test_results/personamem_v2/personamem_v2_assistant_eval_results_20260509_013724.json",
    },
    "GLM-5-Turbo": {
        "username": "GLM-5-Turbo-persona66",
        "user_id": "02481aa6-272a-419f-9a79-5c6bdae1ea44",
        "result_json": "test_results/personamem_v2/personamem_v2_assistant_eval_results_20260508_030837.json",
    },
}


SOURCE_BUCKET_RULES: list[tuple[str, str]] = [
    ("ask_to_forget", r"\bforget\b|do not remember"),
    ("sensitive_info", r"\bDMV\b|Real ID|credit card|card number|email address|@|inhaler|appendectomy|concussion"),
    ("third_person_narrative", r"\bLena\b|\bDaniel\b|\bRachel\b|\bMelissa\b|\bElla\b|\bJulia\b"),
    ("therapy_background", r"anxiety|nightmare|therapist|scary|trauma|jumpy|tense|calm|afraid|panic|CPR|paramedic"),
    ("quoted_personal_fact", r"email|translate|translation|make this|sound better|polished|refined|story|passage"),
    ("ordinary_preference", r"enjoys|likes|prefers|wants|visits|wears"),
]


HIGH_VALUE_BUCKETS = {
    "ask_to_forget",
    "sensitive_info",
    "third_person_narrative",
    "therapy_background",
    "quoted_personal_fact",
    "ordinary_preference",
}


@dataclass
class RowSource:
    row_index: int
    question: str
    supporting_preference: str
    related_conversation_snippet: str
    pref_type: str
    source_bucket: str
    ideal_granularity: str


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.lower()).strip()


def tokens(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-zA-Z0-9]+", normalize_text(value))
        if len(token) >= 3
    }


def overlap_score(left: str, right: str) -> float:
    left_tokens = tokens(left)
    right_tokens = tokens(right)
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens)


def compact(value: str | None, limit: int = 260) -> str:
    if not value:
        return ""
    value = re.sub(r"\s+", " ", value).strip()
    if len(value) <= limit:
        return value
    return value[: limit - 3] + "..."


def load_sources(result_path: Path) -> dict[int, RowSource]:
    data = json.loads(result_path.read_text(encoding="utf-8"))
    rows: dict[int, RowSource] = {}
    for item in data["samples"][0]["qa_results"]:
        row_index = int(item["row_index"])
        source_text = " ".join(
            [
                str(item.get("question") or ""),
                str(item.get("supporting_preference") or ""),
                str(item.get("related_conversation_snippet") or ""),
                str(item.get("pref_type") or ""),
            ]
        )
        bucket = classify_source_bucket(source_text, str(item.get("pref_type") or ""))
        rows[row_index] = RowSource(
            row_index=row_index,
            question=str(item.get("question") or ""),
            supporting_preference=str(item.get("supporting_preference") or ""),
            related_conversation_snippet=str(item.get("related_conversation_snippet") or ""),
            pref_type=str(item.get("pref_type") or ""),
            source_bucket=bucket,
            ideal_granularity=ideal_granularity_for(bucket),
        )
    return rows


def classify_source_bucket(source_text: str, pref_type: str) -> str:
    if pref_type == "ask_to_forget":
        return "ask_to_forget"
    if pref_type in {"therapy_background", "health_and_medical"}:
        return "therapy_background"
    if pref_type == "sensitive_info":
        return "sensitive_info"
    for bucket, pattern in SOURCE_BUCKET_RULES:
        if re.search(pattern, source_text, re.IGNORECASE):
            return bucket
    return "low_value_task_shell"


def ideal_granularity_for(bucket: str) -> str:
    if bucket == "low_value_task_shell":
        return "coarse_only"
    if bucket == "ask_to_forget":
        return "negative_constraint"
    if bucket == "sensitive_info":
        return "sensitive_guarded"
    if bucket in {"therapy_background", "quoted_personal_fact", "third_person_narrative", "ordinary_preference"}:
        return "coarse_plus_atomic"
    return "coarse_plus_atomic"


async def export_snapshot(model: str, info: dict[str, str]) -> dict[str, Any]:
    user_id = info["user_id"]
    async with AsyncSessionLocal() as session:
        user = (await session.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
        resources = list(
            (
                await session.execute(
                    select(Resource)
                    .where(Resource.user_id == user_id)
                    .order_by(Resource.created_at, Resource.id)
                )
            )
            .scalars()
            .all()
        )
        categories = list(
            (
                await session.execute(
                    select(Category)
                    .where(Category.user_id == user_id)
                    .order_by(Category.created_at, Category.id)
                )
            )
            .scalars()
            .all()
        )
        resource_ids = [resource.id for resource in resources]
        links = []
        if resource_ids:
            links = list(
                (
                    await session.execute(
                        select(ResourceCategory)
                        .where(ResourceCategory.resource_id.in_(resource_ids))
                        .order_by(ResourceCategory.created_at, ResourceCategory.id)
                    )
                )
                .scalars()
                .all()
            )
        return {
            "model": model,
            "username": info["username"],
            "user_id": user_id,
            "db_username": user.username if user else None,
            "resources": [
                {
                    "id": r.id,
                    "raw_content": r.raw_content,
                    "description": r.description,
                    "assistant_response": r.assistant_response,
                    "importance_score": r.importance_score,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in resources
            ],
            "categories": [
                {
                    "id": c.id,
                    "category_name": c.category_name,
                    "content": c.content,
                    "importance_score": c.importance_score,
                    "created_at": c.created_at.isoformat() if c.created_at else None,
                }
                for c in categories
            ],
            "resource_categories": [
                {
                    "id": link.id,
                    "resource_id": link.resource_id,
                    "category_id": link.category_id,
                    "relation_type": link.relation_type,
                    "note": link.note,
                    "created_at": link.created_at.isoformat() if link.created_at else None,
                }
                for link in links
            ],
        }


def align_snapshot(snapshot: dict[str, Any], sources: dict[int, RowSource]) -> list[dict[str, Any]]:
    links_by_resource: dict[str, list[str]] = defaultdict(list)
    for link in snapshot["resource_categories"]:
        links_by_resource[link["resource_id"]].append(link["category_id"])
    categories_by_id = {category["id"]: category for category in snapshot["categories"]}

    aligned = []
    for resource in snapshot["resources"]:
        haystack = " ".join(
            [
                resource.get("raw_content") or "",
                resource.get("description") or "",
                resource.get("assistant_response") or "",
            ]
        )
        best_row = None
        best_score = 0.0
        for row in sources.values():
            source_text = " ".join(
                [
                    row.related_conversation_snippet,
                    row.supporting_preference,
                    row.question,
                ]
            )
            score = max(overlap_score(haystack, source_text), overlap_score(source_text, haystack))
            if score > best_score:
                best_row = row
                best_score = score
        linked_categories = [
            categories_by_id[cid]
            for cid in links_by_resource.get(resource["id"], [])
            if cid in categories_by_id
        ]
        aligned.append(
            {
                "model": snapshot["model"],
                "resource_id": resource["id"],
                "row_index": best_row.row_index if best_row else None,
                "alignment_score": round(best_score, 4),
                "source_bucket": best_row.source_bucket if best_row else "unassigned",
                "ideal_granularity": best_row.ideal_granularity if best_row else "unassigned",
                "resource_description": resource.get("description") or "",
                "resource_raw_content": resource.get("raw_content") or "",
                "category_count": len(linked_categories),
                "categories": linked_categories,
            }
        )
    return aligned


def summarize_model(snapshot: dict[str, Any], aligned: list[dict[str, Any]]) -> dict[str, Any]:
    category_distribution = Counter(category["category_name"] for category in snapshot["categories"])
    bucket_resource_counts = Counter(item["source_bucket"] for item in aligned)
    bucket_category_counts: Counter[str] = Counter()
    low_value_over_extracted = 0
    high_value_without_category = 0
    suspicious_misattribution = 0
    sensitive_raw_mentions = 0

    sensitive_terms = re.compile(r"Real ID|credit card|card number|@|MN-REALID|\\d{4}\\s+\\d{4}", re.IGNORECASE)
    third_person_names = re.compile(r"\\b(Lena|Daniel|Rachel|Melissa|Ella|Julia)\\b", re.IGNORECASE)

    for item in aligned:
        bucket_category_counts[item["source_bucket"]] += item["category_count"]
        if item["source_bucket"] == "low_value_task_shell" and item["category_count"] > 0:
            low_value_over_extracted += 1
        if item["source_bucket"] in HIGH_VALUE_BUCKETS and item["category_count"] == 0:
            high_value_without_category += 1
        category_text = " ".join(category["content"] for category in item["categories"])
        if third_person_names.search(category_text) and "user described" not in category_text.lower():
            suspicious_misattribution += 1
        if sensitive_terms.search(category_text):
            sensitive_raw_mentions += 1

    return {
        "model": snapshot["model"],
        "resources": len(snapshot["resources"]),
        "categories": len(snapshot["categories"]),
        "links": len(snapshot["resource_categories"]),
        "category_distribution": dict(category_distribution),
        "bucket_resource_counts": dict(bucket_resource_counts),
        "bucket_category_counts": dict(bucket_category_counts),
        "low_value_over_extracted_resources": low_value_over_extracted,
        "high_value_resources_without_category": high_value_without_category,
        "suspicious_misattribution_resources": suspicious_misattribution,
        "sensitive_raw_mention_resources": sensitive_raw_mentions,
    }


def write_outputs(
    output_dir: Path,
    snapshots: dict[str, dict[str, Any]],
    aligned_by_model: dict[str, list[dict[str, Any]]],
    summaries: list[dict[str, Any]],
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    snapshot_dir = output_dir / "db_snapshots"
    snapshot_dir.mkdir(exist_ok=True)
    for model, snapshot in snapshots.items():
        (snapshot_dir / f"{safe_name(model)}.json").write_text(
            json.dumps(snapshot, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    matrix_path = output_dir / "adaptive_granularity_matrix.csv"
    with matrix_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "model",
                "row_index",
                "resource_id",
                "alignment_score",
                "source_bucket",
                "ideal_granularity",
                "category_count",
                "resource_description_preview",
                "category_preview",
            ],
        )
        writer.writeheader()
        for aligned in aligned_by_model.values():
            for item in aligned:
                writer.writerow(
                    {
                        "model": item["model"],
                        "row_index": item["row_index"],
                        "resource_id": item["resource_id"],
                        "alignment_score": item["alignment_score"],
                        "source_bucket": item["source_bucket"],
                        "ideal_granularity": item["ideal_granularity"],
                        "category_count": item["category_count"],
                        "resource_description_preview": compact(item["resource_description"]),
                        "category_preview": " || ".join(compact(c["content"], 160) for c in item["categories"][:3]),
                    }
                )

    (output_dir / "summary.json").write_text(
        json.dumps({"models": summaries}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    lines = ["# PersonaMem-v2 Storage Granularity Review Draft", ""]
    for summary in summaries:
        lines.extend(
            [
                f"## {summary['model']}",
                "",
                f"- resources: {summary['resources']}",
                f"- categories: {summary['categories']}",
                f"- links: {summary['links']}",
                f"- category_distribution: `{summary['category_distribution']}`",
                f"- bucket_resource_counts: `{summary['bucket_resource_counts']}`",
                f"- bucket_category_counts: `{summary['bucket_category_counts']}`",
                f"- low_value_over_extracted_resources: {summary['low_value_over_extracted_resources']}",
                f"- high_value_resources_without_category: {summary['high_value_resources_without_category']}",
                f"- suspicious_misattribution_resources: {summary['suspicious_misattribution_resources']}",
                f"- sensitive_raw_mention_resources: {summary['sensitive_raw_mention_resources']}",
                "",
            ]
        )
    (output_dir / "model_storage_comparison_draft.md").write_text(
        "\n".join(lines),
        encoding="utf-8",
    )


def safe_name(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]+", "_", value)


def load_model_config(config_path: Path | None) -> dict[str, dict[str, str]]:
    if config_path is None:
        return MODELS
    data = json.loads(config_path.read_text(encoding="utf-8"))
    models = data.get("models", data)
    if not isinstance(models, dict):
        raise ValueError("Model config must be an object or contain a 'models' object.")
    normalized: dict[str, dict[str, str]] = {}
    for model, info in models.items():
        if not isinstance(info, dict):
            raise ValueError(f"Model config for {model!r} must be an object.")
        required = {"username", "user_id", "result_json"}
        missing = required - set(info)
        if missing:
            raise ValueError(f"Model config for {model!r} missing keys: {sorted(missing)}")
        normalized[str(model)] = {
            "username": str(info["username"]),
            "user_id": str(info["user_id"]),
            "result_json": str(info["result_json"]),
        }
    return normalized


async def run(output_dir: Path, model_config: dict[str, dict[str, str]]) -> None:
    first_result = next(iter(model_config.values()))["result_json"]
    sources = load_sources(Path(first_result))
    snapshots: dict[str, dict[str, Any]] = {}
    aligned_by_model: dict[str, list[dict[str, Any]]] = {}
    summaries: list[dict[str, Any]] = []
    for model, info in model_config.items():
        snapshot = await export_snapshot(model, info)
        aligned = align_snapshot(snapshot, sources)
        summary = summarize_model(snapshot, aligned)
        snapshots[model] = snapshot
        aligned_by_model[model] = aligned
        summaries.append(summary)
    write_outputs(output_dir, snapshots, aligned_by_model, summaries)
    print(f"Wrote storage review artifacts to {output_dir}")
    for summary in summaries:
        print(
            summary["model"],
            "resources=",
            summary["resources"],
            "categories=",
            summary["categories"],
            "low_value_over=",
            summary["low_value_over_extracted_resources"],
            "high_value_without_category=",
            summary["high_value_resources_without_category"],
            "sensitive_raw=",
            summary["sensitive_raw_mention_resources"],
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        default="test_results/personamem_v2_storage_review",
    )
    parser.add_argument(
        "--model-config",
        default=None,
        help="Optional JSON model config with username, user_id, and result_json per model.",
    )
    args = parser.parse_args()
    asyncio.run(run(Path(args.output_dir), load_model_config(Path(args.model_config) if args.model_config else None)))


if __name__ == "__main__":
    main()
