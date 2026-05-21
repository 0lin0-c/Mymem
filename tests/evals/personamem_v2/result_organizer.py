from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any


REPORT_EXTENSIONS = {".json", ".md"}
LOG_EXTENSIONS = {".log", ".pid", ".out", ".err", ".txt", ".ps1"}


def plan_organization(root: Path) -> list[dict[str, Any]]:
    moves: list[dict[str, Any]] = []
    archive_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    for path in sorted(root.iterdir() if root.exists() else []):
        if path.is_dir():
            continue
        target_subdir = _target_subdir(path)
        destination = root / target_subdir / archive_id / path.name
        moves.append(
            {
                "old_path": str(path),
                "new_path": str(destination),
                "size": path.stat().st_size,
                "sha256": _sha256(path),
            }
        )
    return moves


def apply_moves(moves: list[dict[str, Any]], *, dry_run: bool) -> None:
    for move in moves:
        old_path = Path(move["old_path"])
        new_path = Path(move["new_path"])
        if dry_run:
            continue
        new_path.parent.mkdir(parents=True, exist_ok=True)
        old_path.replace(new_path)


def write_manifest(root: Path, moves: list[dict[str, Any]], *, dry_run: bool) -> Path:
    manifest_dir = root / "logs"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    suffix = "dry_run" if dry_run else "applied"
    path = manifest_dir / f"moved_artifacts_manifest_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{suffix}.json"
    payload = {
        "root": str(root),
        "dry_run": dry_run,
        "moves": moves,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _target_subdir(path: Path) -> str:
    suffix = path.suffix.lower()
    name = path.name.lower()
    root_name = path.parent.name.lower()
    if suffix in LOG_EXTENSIONS or "log" in name:
        return "logs"
    if ("official" in name or "official" in root_name) and suffix in REPORT_EXTENSIONS:
        return "official"
    if "diagnostic" in name or "rerank" in name or "bm25" in name or "candidate" in name:
        return "diagnostic"
    if suffix in REPORT_EXTENSIONS:
        return "legacy"
    return "scratch"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
