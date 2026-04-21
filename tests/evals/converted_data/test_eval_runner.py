from __future__ import annotations

from pathlib import Path

import pytest

from services.llm.factory import LLMFactory
from tests.evals.converted_data.runner import EvalMode, OUTPUT_DIR, run_single_sample
from tests.evals.converted_data.reporting import generate_analysis_markdown, save_results_json


@pytest.mark.converted_data
@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.asyncio
async def test_converted_data_eval(pytestconfig: pytest.Config):
    """Pytest-controlled entrypoint for converted-data memory evaluations."""
    sample = pytestconfig.getoption("--converted-sample")
    run_all = pytestconfig.getoption("--converted-all")
    eval_mode = EvalMode(pytestconfig.getoption("--converted-eval-mode"))
    data_dir_option = pytestconfig.getoption("--converted-data-dir")
    data_dir = Path(data_dir_option) if data_dir_option else None
    character = pytestconfig.getoption("--converted-character")
    top_k = pytestconfig.getoption("--converted-top-k")
    import_only = pytestconfig.getoption("--converted-import-only")
    retrieval_only = pytestconfig.getoption("--converted-retrieval-only")
    reset_memory = pytestconfig.getoption("--converted-reset-memory")
    enable_dedup = not pytestconfig.getoption("--converted-no-dedup")
    max_questions = pytestconfig.getoption("--converted-max-questions")
    postprocess_bad_cases = pytestconfig.getoption("--converted-postprocess-bad-cases")

    if not run_all and sample is None:
        pytest.skip(
            "converted_data eval is opt-in. Use --converted-sample N or --converted-all."
        )

    if data_dir:
        from tests.evals.converted_data import runner

        runner.DATA_DIR = data_dir
        runner.ONBOARDING_PROFILES_FILE = data_dir / "sample_0_onboarding_profiles.json"

    if run_all:
        from tests.evals.converted_data.runner import run_all_samples

        await run_all_samples(
            import_only=import_only,
            retrieval_only=retrieval_only,
            enable_dedup=enable_dedup,
            reset_memory=reset_memory,
            eval_mode=eval_mode,
            max_questions=max_questions,
            postprocess_bad_cases=postprocess_bad_cases,
        )
        return

    reports = await run_single_sample(
        sample,
        import_only=import_only,
        retrieval_only=retrieval_only,
        enable_dedup=enable_dedup,
        top_k=top_k,
        character_filter=character,
        reset_memory=reset_memory,
        eval_mode=eval_mode,
        max_questions=max_questions,
        postprocess_bad_cases=postprocess_bad_cases,
    )
    if not import_only:
        assert reports
        results_path = save_results_json(reports, OUTPUT_DIR, eval_mode=eval_mode.value)
        llm = LLMFactory.get_provider()
        analysis_path = await generate_analysis_markdown(llm, results_path)
        assert analysis_path is not None
