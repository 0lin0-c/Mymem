# Scripts

Prefer pytest for official tests and evaluations. Scripts in this directory are
for setup, local maintenance, compatibility wrappers, or diagnostics.

## Compatibility Wrappers

These preserve existing local workflows but should not be copied for new
official evaluation entrypoints:

- `run_converted_data_eval.py`
- `run_personamem_v2_eval.py`
- `run_personamem_v2_rerank_eval.py`
- `run_personamem_v2_candidate_experiment.py`
- `run_personamem_v2_candidate_views.py`

New official evaluation options should be registered in `tests/conftest.py` and
run through `pytest`.

## Maintenance

- `init_db.py`
- `check_db.py`
- `check_categories.py`
- `clean_user.py`
- `clean_user_direct.py`
- `query_db.py`
- `fix_persona_template.py`
- `fix_user_templates.py`

## Dataset Utilities

- `shift_converted_data_dates.py`
- `shift_converted_data_to_recent_window.py`
- `trim_repeated_names_in_converted_data.py`

## Legacy Diagnostics

Historical one-off analysis scripts live under `scripts/legacy_diagnostics/`.
They may reference old files under `test_results/**/legacy` and should not be
treated as supported control-plane entrypoints.
