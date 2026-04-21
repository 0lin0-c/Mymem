"""CLI entrypoint for converted-data memory evaluations.

Usage:
    # Run single sample
    uv run python scripts/run_converted_data_eval.py --sample 0

    # Run all samples
    uv run python scripts/run_converted_data_eval.py --all

    # Import only
    uv run python scripts/run_converted_data_eval.py --sample 0 --import-only
"""

from tests.evals.converted_data.runner import main

if __name__ == "__main__":
    main()
