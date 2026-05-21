import json

from tests.evals.personamem_v2.result_organizer import plan_organization, write_manifest


def test_personamem_results_organizer_plans_moves_without_deleting(tmp_path):
    (tmp_path / "result.json").write_text("{}", encoding="utf-8")
    (tmp_path / "run.log").write_text("log", encoding="utf-8")
    (tmp_path / "bm25_eval.json").write_text("{}", encoding="utf-8")

    moves = plan_organization(tmp_path)

    assert len(moves) == 3
    assert any("/legacy/" in move["new_path"].replace("\\", "/") for move in moves)
    assert any("/logs/" in move["new_path"].replace("\\", "/") for move in moves)
    assert any("/diagnostic/" in move["new_path"].replace("\\", "/") for move in moves)
    assert all(move["sha256"] for move in moves)
    assert (tmp_path / "result.json").exists()


def test_personamem_results_organizer_writes_dry_run_manifest(tmp_path):
    (tmp_path / "result.json").write_text("{}", encoding="utf-8")
    moves = plan_organization(tmp_path)

    manifest = write_manifest(tmp_path, moves, dry_run=True)
    payload = json.loads(manifest.read_text(encoding="utf-8"))

    assert payload["dry_run"] is True
    assert payload["moves"][0]["old_path"].endswith("result.json")
