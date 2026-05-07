from types import SimpleNamespace

from tests.conftest import (
    _converted_eval_requires_write,
    _looks_like_real_database,
)


def test_looks_like_real_database_detects_real_postgres_url():
    assert _looks_like_real_database(
        "postgresql+asyncpg://postgres:secret@192.168.31.95:46195/postgres"
    ) is True


def test_looks_like_real_database_ignores_test_database_url():
    assert _looks_like_real_database(
        "postgresql+asyncpg://postgres:secret@localhost:5432/mymem_test"
    ) is False


def test_converted_eval_requires_write_for_import_path():
    config = SimpleNamespace(
        getoption=lambda name: {
            "--converted-retrieval-only": False,
            "--converted-import-only": False,
            "--converted-reset-memory": False,
        }[name]
    )
    assert _converted_eval_requires_write(config) is True


def test_converted_eval_requires_write_false_for_read_only_path():
    config = SimpleNamespace(
        getoption=lambda name: {
            "--converted-retrieval-only": True,
            "--converted-import-only": False,
            "--converted-reset-memory": False,
        }[name]
    )
    assert _converted_eval_requires_write(config) is False
