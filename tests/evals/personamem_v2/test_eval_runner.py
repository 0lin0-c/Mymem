from __future__ import annotations

from argparse import Namespace
from pathlib import Path

import pytest

from core.config import settings
from tests.conftest import _assert_real_db_usage_is_safe
from tests.evals.personamem_v2.models import EvalMode
from tests.evals.personamem_v2.orthogonal_eval import (
    OUTPUT_DIR as ORTHOGONAL_OUTPUT_DIR,
    load_json_file,
    run_orthogonal_from_config,
)
from tests.evals.personamem_v2.runner import (
    parse_model_sweep,
    run_personamem_v2_eval,
    run_personamem_v2_model_sweep,
)


@pytest.mark.personamem_v2
@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.asyncio
async def test_personamem_v2_eval(pytestconfig: pytest.Config):
    """Pytest-controlled entrypoint for PersonaMem-v2 text snippet evaluations."""
    enabled = pytestconfig.getoption("--personamem-v2")
    if not enabled:
        pytest.skip("PersonaMem-v2 eval is opt-in. Use --personamem-v2.")
    _assert_real_db_usage_is_safe(pytestconfig)

    if pytestconfig.getoption("--personamem-v2-orthogonal"):
        baseline_path = pytestconfig.getoption("--personamem-v2-baseline-snapshot")
        config_path = pytestconfig.getoption("--personamem-v2-candidate-config")
        if not baseline_path or not config_path:
            pytest.fail(
                "--personamem-v2-orthogonal requires --personamem-v2-baseline-snapshot "
                "and --personamem-v2-candidate-config."
            )
        output_dir_option = pytestconfig.getoption("--personamem-v2-output-dir")
        result = run_orthogonal_from_config(
            mode=pytestconfig.getoption("--personamem-v2-orthogonal-mode"),
            baseline_snapshot=load_json_file(baseline_path),
            candidate_config=load_json_file(config_path),
            output_dir=Path(output_dir_option) if output_dir_option else ORTHOGONAL_OUTPUT_DIR,
        )
        assert result["run_manifest"]
        return

    diagnostic_rerank = pytestconfig.getoption("--personamem-v2-diagnostic-rerank")
    if diagnostic_rerank:
        args = _diagnostic_rerank_args(pytestconfig)
        output_dir_option = pytestconfig.getoption("--personamem-v2-output-dir")
        output_dir = Path(output_dir_option) if output_dir_option else None
        if diagnostic_rerank == "glm":
            from tests.evals.personamem_v2.rerank_eval import run_eval, write_rerank_report

            report = await run_eval(args)
            json_path, _ = write_rerank_report(report, output_dir or Path("test_results/personamem_v2"))
        else:
            from tests.evals.personamem_v2.bm25_eval import run_eval, write_bm25_report

            report = await run_eval(args)
            json_path, _ = write_bm25_report(report, output_dir or Path("test_results/personamem_v2"))
        assert report["formal_ab_eligible"] is False
        assert report["experiment_conclusion"] == "diagnostic_only"
        assert report["run_manifest"]["result_file_path"] == str(json_path)
        return

    context_snapshot_path = pytestconfig.getoption("--personamem-v2-generator-replay-context-snapshot")
    if context_snapshot_path:
        chat_model = pytestconfig.getoption("--personamem-v2-generator-replay-chat-model")
        if not chat_model:
            pytest.fail(
                "--personamem-v2-generator-replay-context-snapshot requires "
                "--personamem-v2-generator-replay-chat-model."
            )
        from tests.evals.personamem_v2.generator_replay_eval import replay_generator_from_context_snapshot

        output_dir_option = pytestconfig.getoption("--personamem-v2-output-dir")
        output_dir = Path(output_dir_option) if output_dir_option else None
        report = await replay_generator_from_context_snapshot(
            load_json_file(context_snapshot_path),
            chat_model=chat_model,
            evaluator_model=pytestconfig.getoption("--personamem-v2-evaluator-model") or settings.chat_model,
            output_dir=output_dir or Path("test_results/personamem_v2/diagnostic/generator_replay"),
        )
        assert report["run_manifest"]["result_file_path"]
        assert report["test_info"]["formal_ab_variant_for"] == "generator_ab"
        assert report["formal_ab_eligible"] is False
        assert report["experiment_conclusion"] == "diagnostic_only"
        return

    model_sweep = parse_model_sweep(pytestconfig.getoption("--personamem-v2-model-sweep"))
    if model_sweep:
        if pytestconfig.getoption("--personamem-v2-chat-model"):
            pytest.fail("--personamem-v2-chat-model cannot be combined with --personamem-v2-model-sweep.")
        output_dir_option = pytestconfig.getoption("--personamem-v2-output-dir")
        result = await run_personamem_v2_model_sweep(
            chat_models=model_sweep,
            split=pytestconfig.getoption("--personamem-v2-split"),
            max_personas=pytestconfig.getoption("--personamem-v2-max-personas"),
            max_questions=pytestconfig.getoption("--personamem-v2-max-questions"),
            max_rows=pytestconfig.getoption("--personamem-v2-max-rows"),
            persona_id=pytestconfig.getoption("--personamem-v2-persona-id"),
            import_only=pytestconfig.getoption("--personamem-v2-import-only"),
            retrieval_only=pytestconfig.getoption("--personamem-v2-retrieval-only"),
            enable_dedup=not pytestconfig.getoption("--personamem-v2-no-dedup"),
            reset_memory=pytestconfig.getoption("--personamem-v2-reset-memory"),
            eval_mode=EvalMode(pytestconfig.getoption("--personamem-v2-eval-mode")),
            top_k=pytestconfig.getoption("--personamem-v2-top-k"),
            save_raw_snapshot=not pytestconfig.getoption("--personamem-v2-no-save-raw-snapshot"),
            evaluator_model=pytestconfig.getoption("--personamem-v2-evaluator-model"),
            output_dir=Path(output_dir_option) if output_dir_option else None,
            question_timeout_seconds=pytestconfig.getoption("--personamem-v2-question-timeout-seconds"),
        )
        if not pytestconfig.getoption("--personamem-v2-import-only"):
            assert result["ranked_models"]
            assert any(item.get("total_questions", 0) > 0 for item in result["ranked_models"])
        return

    chat_model = pytestconfig.getoption("--personamem-v2-chat-model")
    output_dir_option = pytestconfig.getoption("--personamem-v2-output-dir")
    reports = await run_personamem_v2_eval(
        split=pytestconfig.getoption("--personamem-v2-split"),
        max_personas=pytestconfig.getoption("--personamem-v2-max-personas"),
        max_questions=pytestconfig.getoption("--personamem-v2-max-questions"),
        max_rows=pytestconfig.getoption("--personamem-v2-max-rows"),
        persona_id=pytestconfig.getoption("--personamem-v2-persona-id"),
        import_only=pytestconfig.getoption("--personamem-v2-import-only"),
        retrieval_only=pytestconfig.getoption("--personamem-v2-retrieval-only"),
        enable_dedup=not pytestconfig.getoption("--personamem-v2-no-dedup"),
        reset_memory=pytestconfig.getoption("--personamem-v2-reset-memory"),
        eval_mode=EvalMode(pytestconfig.getoption("--personamem-v2-eval-mode")),
        top_k=pytestconfig.getoption("--personamem-v2-top-k"),
        save_raw_snapshot=not pytestconfig.getoption("--personamem-v2-no-save-raw-snapshot"),
        chat_model=chat_model,
        evaluator_model=pytestconfig.getoption("--personamem-v2-evaluator-model"),
        output_dir=Path(output_dir_option) if output_dir_option else None,
        question_timeout_seconds=pytestconfig.getoption("--personamem-v2-question-timeout-seconds"),
    )
    if not pytestconfig.getoption("--personamem-v2-import-only"):
        assert reports
        assert sum(report.total_questions for report in reports) > 0
        assert all(report.total_questions == len(report.results) for report in reports)


def _diagnostic_rerank_args(pytestconfig: pytest.Config) -> Namespace:
    input_path = pytestconfig.getoption("--personamem-v2-input-retrieval-json")
    output_dir = pytestconfig.getoption("--personamem-v2-output-dir")
    return Namespace(
        split=pytestconfig.getoption("--personamem-v2-split"),
        persona_id=pytestconfig.getoption("--personamem-v2-persona-id") or "66",
        username=None,
        max_rows=pytestconfig.getoption("--personamem-v2-max-rows"),
        max_questions=pytestconfig.getoption("--personamem-v2-max-questions"),
        retrieve_top_k=pytestconfig.getoption("--personamem-v2-retrieve-top-k"),
        answer_top_k=pytestconfig.getoption("--personamem-v2-answer-top-k"),
        rerank_model=pytestconfig.getoption("--personamem-v2-rerank-model"),
        timeout=60,
        bm25_k1=pytestconfig.getoption("--personamem-v2-bm25-k1"),
        bm25_b=pytestconfig.getoption("--personamem-v2-bm25-b"),
        input_retrieval_json=Path(input_path) if input_path else None,
        output_dir=Path(output_dir) if output_dir else Path("test_results/personamem_v2"),
    )
