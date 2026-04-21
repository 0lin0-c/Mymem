# Evaluation Tests

This directory is for dataset-driven evaluations. These tests may be slower than unit or contract tests and may depend on larger fixtures, a real database, or real model providers.

Use this layer to measure behavior, not to define product logic. If an evaluation discovers a better product behavior, promote that behavior into `services/` and make the evaluation call the shared service.

