from __future__ import annotations

from pathlib import Path

import pytest

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

    model_sweep = parse_model_sweep(pytestconfig.getoption("--personamem-v2-model-sweep"))
    if model_sweep:
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
        )
        if not pytestconfig.getoption("--personamem-v2-import-only"):
            assert result["ranked_models"]
        return

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
        evaluator_model=pytestconfig.getoption("--personamem-v2-evaluator-model"),
    )
    if not pytestconfig.getoption("--personamem-v2-import-only"):
        assert reports
