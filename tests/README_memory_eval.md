# Mymem Memory Evaluation Modes

This test suite separates project tests into four layers:

1. Unit tests
   - Test pure logic such as date parsing, language guards, score helpers, and prompt fragments.
   - These should not call real LLMs or depend on the full converted-data harness.

2. Contract tests
   - Test service boundaries such as `MemoryWriter.save_chat`, `MemoryRetriever.retrieve`, and `ProfileService.onboarding`.
   - Use fake or controlled providers when the exact output must be deterministic.

3. Integration evaluations
   - Test a real slice of the Mymem stack with real DB/repository/service calls.
   - `pytest tests/evals/converted_data --converted-eval-mode storage_eval --converted-sample 0` and `--converted-eval-mode retrieval_eval` belong here.

4. End-to-end assistant evaluations
   - Test the user-visible assistant behavior.
   - `pytest tests/evals/converted_data --converted-eval-mode assistant_eval --converted-sample 0` is the official converted-data form.
   - Assistant answer generation should call `ChatOrchestrator` or the real chat path.
   - Assistant evaluations may inspect `ChatOrchestrator` trace for debugging and scoring, but normal `/v1/chat` responses must not expose retrieved trace to end users.

## Official Control Plane

Use `pytest` as the official control plane for memory evaluations. This keeps unit tests, contract tests, integration evals, and assistant evals under one discovery, marker, fixture, and CI system.

Directory conventions:

- Test and eval code lives under `tests/`.
- Eval input fixtures live under `tests/fixtures/`.
- Runtime artifacts live under `test_results/<domain>/`.
- Embedding and resource caches live under `test_results/cache/`.

The legacy command below remains as a compatibility wrapper only:

```bash
python -m tests.test_converted_data --sample 0 --eval-mode retrieval_eval
```

New eval modules should not add their own standalone `argparse` control plane. If a new option is needed, add it through `tests/conftest.py` so every test module can be managed consistently.

Common converted-data examples:

```bash
pytest tests/evals/converted_data --converted-sample 0 --converted-eval-mode storage_eval
pytest tests/evals/converted_data --converted-sample 0 --converted-eval-mode retrieval_eval
pytest tests/evals/converted_data --converted-sample 0 --converted-eval-mode assistant_eval
pytest tests/evals/converted_data --converted-sample 0 --converted-character caroline --converted-top-k 10
```

只读 A/B 检索调参验证工具：

```bash
python -m tests.evals.converted_data.retrieval_tuning_ab --sample 0 --data-dir data/converted_data_recent_2026q1_name_trimmed --character caroline
```

该工具不会重新导入数据，也不会调用会自增 `access_count` 的正式 `retrieve()` 写路径；它只读复现检索步骤，用于比较：
- 旧 scoring + top_k=5
- 新 scoring + top_k=5
- 旧 scoring + top_k=10
- 新 scoring + top_k=10

## Runtime Safety

When using the real database, treat command modes as permission modes:

- Read-only evals:
  - use `--converted-retrieval-only`
  - allowed to read real DB data
  - must not reset/import memory
- Write-path evals:
  - re-import / reset memory
  - must be explicitly intended
  - when running through `pytest`, also require `--allow-real-db-write`

Examples:

```bash
# Read-only evaluation on real DB
pytest tests/evals/converted_data --converted-sample 0 --converted-eval-mode assistant_eval --converted-character caroline --converted-retrieval-only

# Explicit write-path evaluation on real DB
pytest tests/evals/converted_data --converted-sample 0 --converted-eval-mode assistant_eval --converted-character caroline --converted-reset-memory --allow-real-db-write
```

Regular unit / service / contract pytest runs should not target the real database unless you explicitly intend to modify it.

## Converted Data Modes

`storage_eval`

- Imports data through the real onboarding and memory-writing path.
- Checks whether expected QA evidence can be found in DB.
- Does not run retrieval or answer generation.

`retrieval_eval`

- Runs `storage_eval` checks first.
- Calls the real `MemoryRetriever.retrieve`.
- Checks whether DB evidence appears in retrieved top-k and records rank.

`assistant_eval`

- Runs retrieval first.
- Generates an answer through `ChatOrchestrator` / the real chat orchestration path.
- Evaluates answer correctness.
- Keeps profile, recent conversation, retrieved memories, priority rules, and trace aligned with real chat behavior.
- By default it uses the real retrieval and real answer-generation path.
- Whether storage runs again depends on the flags:
  - default run: imports data and then evaluates
  - `--converted-retrieval-only`: skips storage import and reuses already imported DB data for retrieval/answer evaluation

## Result JSON Shape

Converted-data evals still write a single result JSON file.

- Top-level fields are now summary-first: `test_info`, `statistics`, `samples`
- `statistics` keeps only decision-relevant metrics for the active mode
- Each `qa_result` keeps:
  - core reading fields such as `question`, `standard_answer`, `generated_answer`, `is_correct`
  - `failure_type`
  - `trace_summary` for quick reading
  - `trace_detail` for full debugging context

This keeps the main reading path compact while preserving full trace data in the same file.

## Rule

Tests may control data, time, DB state, and fake providers. Tests should not permanently duplicate product business logic. If an experimental test path works better, promote it into the real service layer and make both API and tests call the same implementation.

In practice:

- Storage evals call the real storage chain.
- Retrieval evals call the real retrieval chain.
- Assistant evals call the real chat/orchestrator chain.
- Test-owned logic is limited to data loading, assertions, oracle judging, reporting, and diagnostics.
