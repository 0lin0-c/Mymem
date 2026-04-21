"""Create a shifted copy of converted_data_zh with dates moved forward.

This is intended for temporary benchmark data. It preserves the original files
and shifts all explicit Gregorian years in converted JSON and QA JSON by a
constant offset.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


YEAR_RE = re.compile(r"\b(20\d{2})\b")
MIN_SHIFT_YEAR = 2010
MAX_SHIFT_YEAR = 2024


def shift_years_in_text(text: str, year_offset: int) -> str:
    """Shift explicit 20xx years in free text by a constant offset."""

    def repl(match: re.Match[str]) -> str:
        year = int(match.group(1))
        if MIN_SHIFT_YEAR <= year <= MAX_SHIFT_YEAR:
            return str(year + year_offset)
        return match.group(1)

    return YEAR_RE.sub(repl, text)


def shift_value(value: Any, year_offset: int) -> Any:
    """Recursively shift explicit years in strings and integer year answers."""
    if isinstance(value, str):
        return shift_years_in_text(value, year_offset)
    if isinstance(value, int) and MIN_SHIFT_YEAR <= value <= MAX_SHIFT_YEAR:
        return value + year_offset
    if isinstance(value, list):
        return [shift_value(item, year_offset) for item in value]
    if isinstance(value, dict):
        return {key: shift_value(item, year_offset) for key, item in value.items()}
    return value


def shift_json_file(src: Path, dst: Path, year_offset: int) -> None:
    data = json.loads(src.read_text(encoding="utf-8"))
    shifted = shift_value(data, year_offset)
    dst.write_text(
        json.dumps(shifted, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def copy_or_shift_file(src: Path, dst: Path, year_offset: int) -> None:
    if src.suffix.lower() == ".json":
        shift_json_file(src, dst, year_offset)
    else:
        dst.write_bytes(src.read_bytes())


def build_shifted_dataset(src_dir: Path, dst_dir: Path, year_offset: int) -> None:
    if not src_dir.exists():
        raise FileNotFoundError(f"Source directory does not exist: {src_dir}")

    dst_dir.mkdir(parents=True, exist_ok=True)

    for src in sorted(src_dir.iterdir()):
        if not src.is_file():
            continue
        copy_or_shift_file(src, dst_dir / src.name, year_offset)

    summary = {
        "source_dir": str(src_dir),
        "year_offset": year_offset,
        "shift_year_range": [MIN_SHIFT_YEAR, MAX_SHIFT_YEAR],
        "note": (
            "Temporary benchmark copy. Explicit years in shift_year_range in JSON strings and "
            "integer year answers were shifted by year_offset."
        ),
    }
    (dst_dir / "date_shift_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Shift converted_data_zh dates into a benchmark copy.")
    parser.add_argument(
        "--src",
        type=Path,
        default=Path("data/converted_data_zh"),
        help="Source converted data directory.",
    )
    parser.add_argument(
        "--dst",
        type=Path,
        default=Path("data/converted_data_shifted_2025"),
        help="Destination directory for shifted data.",
    )
    parser.add_argument(
        "--year-offset",
        type=int,
        default=2,
        help="Year offset to apply. Default +2 maps 2023 to 2025.",
    )
    args = parser.parse_args()

    build_shifted_dataset(args.src, args.dst, args.year_offset)
    print(f"Shifted dataset written to: {args.dst}")


if __name__ == "__main__":
    main()
