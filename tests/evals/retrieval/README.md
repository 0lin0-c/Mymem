# Retrieval Evaluations

TODO:

- Add pytest-managed retrieval evaluations here.
- Call the real `MemoryRetriever` or production-equivalent retrieval entrypoint.
- Do not duplicate SQL scoring, embedding similarity, or ranking logic in tests.
- Keep trace inspection and ranking diagnostics as test-owned oracle/reporting code.
