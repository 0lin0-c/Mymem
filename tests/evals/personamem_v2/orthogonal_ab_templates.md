# PersonaMem-v2 Orthogonal A/B Templates

This file defines the official reusable configuration pattern for PersonaMem-v2
orthogonal replay. These templates are documentation fixtures: copy them into a
scratch config file, fill the snapshot paths and hashes, then run through the
pytest control plane or `run_orthogonal_from_config()`.

## Formal Rules

- A formal A/B changes exactly one layer: `writer`, `retrieval`, `rerank`, or `generator`.
- `e2e_diagnostic` is never a formal A/B, even when it has paired rows.
- Every formal config must provide non-empty provenance:
  `db_snapshot_id`, `dataset_hash`, `cache_hash`, `result_file_path`,
  `chat_model`, `evaluator_model`, `embedding_model`, `temperature`, and `top_k`.
- `controlled_layers` must list every layer that is held fixed.
- Model sweep, GLM rerank, BM25 rerank, and candidate projection wrappers are
  diagnostic unless they emit this orthogonal contract.
- Formal reports must pass `validate_personamem_report_contract(..., require_formal_ab=True)`.

## Retrieval A/B

```json
{
  "experiment_type": "retrieval_ab",
  "changed_layer": "retrieval",
  "controlled_layers": ["writer", "rerank", "generator", "evaluator"],
  "baseline_variant": {
    "name": "current_retrieval",
    "retrieval_config": {"type": "current_topk"}
  },
  "candidate_variant": {
    "name": "answer_bearing_retrieval",
    "retrieval_config": {"type": "answer_bearing_policy"}
  },
  "db_snapshot_id": "personamem_v2_persona66_writer_snapshot_YYYYMMDD",
  "dataset_hash": "<stable dataset hash>",
  "cache_hash": "<stable replay cache hash>",
  "result_file_path": "test_results/personamem_v2_official/official/retrieval_ab.json",
  "chat_model": "<fixed answer model>",
  "embedding_model": "<fixed embedding model>",
  "evaluator_model": "<fixed evaluator model>",
  "temperature": 0,
  "top_k": 5
}
```

## Rerank A/B

```json
{
  "experiment_type": "rerank_ab",
  "changed_layer": "rerank",
  "controlled_layers": ["writer", "retrieval", "generator", "evaluator"],
  "baseline_variant": {
    "name": "current_topk",
    "rerank_config": {"type": "none"}
  },
  "candidate_variant": {
    "name": "answer_bearing_rerank",
    "rerank_config": {"type": "answer_bearing", "top_n": 5}
  },
  "rerank_config": {"type": "answer_bearing", "top_n": 5},
  "db_snapshot_id": "personamem_v2_persona66_fixed_retrieval_snapshot_YYYYMMDD",
  "dataset_hash": "<stable dataset hash>",
  "cache_hash": "<stable replay cache hash>",
  "result_file_path": "test_results/personamem_v2_official/official/rerank_ab.json",
  "chat_model": "<fixed answer model>",
  "embedding_model": "<fixed embedding model>",
  "evaluator_model": "<fixed evaluator model>",
  "temperature": 0,
  "top_k": 5
}
```

## Writer A/B

```json
{
  "experiment_type": "writer_ab",
  "changed_layer": "writer",
  "controlled_layers": ["retrieval", "rerank", "generator", "evaluator"],
  "baseline_variant": {
    "name": "prompt_only_writer",
    "writer_config": {"type": "current_prompt"}
  },
  "candidate_variant": {
    "name": "post_parse_validated_writer",
    "writer_config": {"type": "post_parse_validator"}
  },
  "db_snapshot_id": "personamem_v2_persona66_writer_ab_snapshot_YYYYMMDD",
  "dataset_hash": "<stable dataset hash>",
  "cache_hash": "<stable replay cache hash>",
  "result_file_path": "test_results/personamem_v2_official/official/writer_ab.json",
  "chat_model": "<fixed answer model>",
  "embedding_model": "<fixed embedding model>",
  "evaluator_model": "<fixed evaluator model>",
  "temperature": 0,
  "top_k": 5
}
```

## Generator A/B

```json
{
  "experiment_type": "generator_ab",
  "changed_layer": "generator",
  "controlled_layers": ["writer", "retrieval", "rerank", "evaluator"],
  "baseline_variant": {
    "name": "baseline_generator",
    "generator_config": {"prompt_version": "current"}
  },
  "candidate_variant": {
    "name": "candidate_generator",
    "generator_config": {"prompt_version": "candidate"}
  },
  "db_snapshot_id": "personamem_v2_persona66_fixed_context_snapshot_YYYYMMDD",
  "dataset_hash": "<stable dataset hash>",
  "cache_hash": "<stable replay cache hash>",
  "result_file_path": "test_results/personamem_v2_official/official/generator_ab.json",
  "chat_model": "<candidate answer model or fixed prompt variant>",
  "embedding_model": "<fixed embedding model>",
  "evaluator_model": "<fixed evaluator model>",
  "temperature": 0,
  "top_k": 5
}
```

## Pytest Control Plane

Use pytest for official runs. Thin scripts are compatibility wrappers only.

```powershell
conda run -n memory_agent python -m pytest -q tests\evals\personamem_v2 --personamem-v2 --personamem-v2-orthogonal --personamem-v2-orthogonal-config path\to\config.json
```

If a wrapper is used for local convenience, the produced report must still carry
`formal_ab_eligible=false` unless it goes through the orthogonal contract above.
