"""Create a recent benchmark copy of converted data in a target date window.

The source dataset spans many months per sample. To place each sample into a
recent window (for example 2026-01-05 to 2026-03-25), this script linearly maps
each sample's original session timeline into the target window and rewrites
explicit dates in converted/QA JSON files.

This is for temporary benchmark data only. It preserves ordering but compresses
calendar intervals.
"""
from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


MONTHS = {
    "January": 1,
    "February": 2,
    "March": 3,
    "April": 4,
    "May": 5,
    "June": 6,
    "July": 7,
    "August": 8,
    "September": 9,
    "October": 10,
    "November": 11,
    "December": 12,
}
MONTH_NAMES = {v: k for k, v in MONTHS.items()}

SESSION_DATE_RE = re.compile(
    r"\b(\d{1,2}:\d{2}\s+[ap]m\s+on\s+)(\d{1,2})\s+([A-Z][a-z]+),\s+(20\d{2})\b",
    re.IGNORECASE,
)
MONTH_DAY_YEAR_RE = re.compile(
    r"\b(" + "|".join(MONTHS) + r")\s+(\d{1,2}),\s+(20\d{2})\b"
)
DAY_MONTH_YEAR_RE = re.compile(
    r"\b(\d{1,2})\s+(" + "|".join(MONTHS) + r"),?\s+(20\d{2})\b"
)
ISO_DATE_RE = re.compile(r"\b(20\d{2})-(\d{1,2})-(\d{1,2})\b")
ZH_DATE_RE = re.compile(r"\b(20\d{2})年(\d{1,2})月(\d{1,2})日\b")
MONTH_YEAR_RE = re.compile(r"\b(" + "|".join(MONTHS) + r")\s+(20\d{2})\b")
YEAR_RE = re.compile(r"\b(20\d{2})\b")

MIN_SHIFT_YEAR = 2010
MAX_SHIFT_YEAR = 2024


@dataclass
class SampleDateMapper:
    sample_id: str
    source_start: datetime
    source_end: datetime
    target_start: datetime
    target_end: datetime

    def map_datetime(self, value: datetime) -> datetime:
        source_span = (self.source_end - self.source_start).total_seconds()
        target_span = (self.target_end - self.target_start).total_seconds()
        if source_span <= 0:
            return self.target_start.replace(hour=value.hour, minute=value.minute)

        ratio = (value - self.source_start).total_seconds() / source_span
        mapped = self.target_start + timedelta(seconds=ratio * target_span)
        return mapped.replace(hour=value.hour, minute=value.minute, second=value.second, microsecond=0)

    def map_date(self, value: datetime) -> datetime:
        source_start = self.source_start.replace(hour=0, minute=0, second=0, microsecond=0)
        source_end = self.source_end.replace(hour=0, minute=0, second=0, microsecond=0)
        target_start = self.target_start.replace(hour=0, minute=0, second=0, microsecond=0)
        target_end = self.target_end.replace(hour=0, minute=0, second=0, microsecond=0)
        source_span = (source_end - source_start).total_seconds()
        target_span = (target_end - target_start).total_seconds()
        if source_span <= 0:
            return target_start
        ratio = (value.replace(hour=0, minute=0, second=0, microsecond=0) - source_start).total_seconds() / source_span
        return target_start + timedelta(seconds=ratio * target_span)

    def map_year(self, year: int) -> int:
        if not (MIN_SHIFT_YEAR <= year <= MAX_SHIFT_YEAR):
            return year
        if self.source_start.year <= year <= self.source_end.year:
            return self.target_start.year
        return year + (self.target_start.year - self.source_start.year)


def should_shift_year(year: int) -> bool:
    return MIN_SHIFT_YEAR <= year <= MAX_SHIFT_YEAR


def parse_session_date(value: str) -> datetime:
    return datetime.strptime(value, "%I:%M %p on %d %B, %Y")


def format_day_month_year(value: datetime) -> str:
    return f"{value.day} {MONTH_NAMES[value.month]} {value.year}"


def format_month_day_year(value: datetime) -> str:
    return f"{MONTH_NAMES[value.month]} {value.day}, {value.year}"


def transform_text(text: str, mapper: SampleDateMapper) -> str:
    def repl_session(match: re.Match[str]) -> str:
        prefix, day, month, year = match.groups()
        if not should_shift_year(int(year)):
            return match.group(0)
        time_text = prefix.lower().replace(" on ", "").strip()
        parsed_time = datetime.strptime(time_text, "%I:%M %p")
        original = datetime(
            int(year),
            MONTHS[month],
            int(day),
            parsed_time.hour,
            parsed_time.minute,
        )
        mapped = mapper.map_datetime(original)
        return f"{prefix}{mapped.day} {MONTH_NAMES[mapped.month]}, {mapped.year}"

    def repl_month_day(match: re.Match[str]) -> str:
        month, day, year = match.groups()
        if not should_shift_year(int(year)):
            return match.group(0)
        mapped = mapper.map_date(datetime(int(year), MONTHS[month], int(day)))
        return format_month_day_year(mapped)

    def repl_day_month(match: re.Match[str]) -> str:
        day, month, year = match.groups()
        if not should_shift_year(int(year)):
            return match.group(0)
        mapped = mapper.map_date(datetime(int(year), MONTHS[month], int(day)))
        return format_day_month_year(mapped)

    def repl_iso(match: re.Match[str]) -> str:
        year, month, day = match.groups()
        if not should_shift_year(int(year)):
            return match.group(0)
        mapped = mapper.map_date(datetime(int(year), int(month), int(day)))
        return mapped.strftime("%Y-%m-%d")

    def repl_zh(match: re.Match[str]) -> str:
        year, month, day = match.groups()
        if not should_shift_year(int(year)):
            return match.group(0)
        mapped = mapper.map_date(datetime(int(year), int(month), int(day)))
        return f"{mapped.year}年{mapped.month}月{mapped.day}日"

    def repl_month_year(match: re.Match[str]) -> str:
        month, year = match.groups()
        if not should_shift_year(int(year)):
            return match.group(0)
        mapped = mapper.map_date(datetime(int(year), MONTHS[month], 15))
        return f"{MONTH_NAMES[mapped.month]} {mapped.year}"

    def repl_year(match: re.Match[str]) -> str:
        return str(mapper.map_year(int(match.group(1))))

    transformed = text
    transformed = SESSION_DATE_RE.sub(repl_session, transformed)
    transformed = MONTH_DAY_YEAR_RE.sub(repl_month_day, transformed)
    transformed = DAY_MONTH_YEAR_RE.sub(repl_day_month, transformed)
    transformed = ISO_DATE_RE.sub(repl_iso, transformed)
    transformed = ZH_DATE_RE.sub(repl_zh, transformed)
    transformed = MONTH_YEAR_RE.sub(repl_month_year, transformed)
    transformed = YEAR_RE.sub(repl_year, transformed)
    return transformed


def transform_value(value: Any, mapper: SampleDateMapper) -> Any:
    if isinstance(value, str):
        return transform_text(value, mapper)
    if isinstance(value, int):
        return mapper.map_year(value)
    if isinstance(value, list):
        return [transform_value(item, mapper) for item in value]
    if isinstance(value, dict):
        return {key: transform_value(item, mapper) for key, item in value.items()}
    return value


def sample_id_from_name(path: Path) -> str | None:
    match = re.match(r"sample_(\d+)_", path.name)
    return match.group(1) if match else None


def build_sample_mappers(src_dir: Path, target_start: datetime, target_end: datetime) -> dict[str, SampleDateMapper]:
    sample_dates: dict[str, list[datetime]] = {}
    for path in src_dir.glob("sample_*_converted.json"):
        sample_id = sample_id_from_name(path)
        if sample_id is None:
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        for session in data.get("sessions", []):
            sample_dates.setdefault(sample_id, []).append(parse_session_date(session["session_date"]))

    mappers = {}
    for sample_id, dates in sample_dates.items():
        mappers[sample_id] = SampleDateMapper(
            sample_id=sample_id,
            source_start=min(dates),
            source_end=max(dates),
            target_start=target_start,
            target_end=target_end,
        )
    return mappers


def transform_file(src: Path, dst: Path, mappers: dict[str, SampleDateMapper]) -> None:
    sample_id = sample_id_from_name(src)
    if src.suffix.lower() != ".json" or sample_id not in mappers:
        dst.write_bytes(src.read_bytes())
        return

    data = json.loads(src.read_text(encoding="utf-8"))
    transformed = transform_value(data, mappers[sample_id])
    dst.write_text(json.dumps(transformed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build_recent_dataset(src_dir: Path, dst_dir: Path, target_start: datetime, target_end: datetime) -> None:
    if not src_dir.exists():
        raise FileNotFoundError(f"Source directory does not exist: {src_dir}")

    dst_dir.mkdir(parents=True, exist_ok=True)
    mappers = build_sample_mappers(src_dir, target_start, target_end)

    for src in sorted(src_dir.iterdir()):
        if src.is_file():
            transform_file(src, dst_dir / src.name, mappers)

    summary = {
        "source_dir": str(src_dir),
        "target_start": target_start.strftime("%Y-%m-%d"),
        "target_end": target_end.strftime("%Y-%m-%d"),
        "note": "Temporary benchmark copy. Each sample timeline is linearly compressed into the target window.",
        "samples": {
            sample_id: {
                "source_start": mapper.source_start.strftime("%Y-%m-%d"),
                "source_end": mapper.source_end.strftime("%Y-%m-%d"),
                "target_start": mapper.target_start.strftime("%Y-%m-%d"),
                "target_end": mapper.target_end.strftime("%Y-%m-%d"),
            }
            for sample_id, mapper in sorted(mappers.items(), key=lambda item: int(item[0]))
        },
    }
    (dst_dir / "recent_window_shift_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Compress converted data dates into a recent benchmark window.")
    parser.add_argument("--src", type=Path, default=Path("data/converted_data_zh"))
    parser.add_argument("--dst", type=Path, default=Path("data/converted_data_recent_2026q1"))
    parser.add_argument("--target-start", default="2026-01-05")
    parser.add_argument("--target-end", default="2026-03-25")
    args = parser.parse_args()

    target_start = datetime.strptime(args.target_start, "%Y-%m-%d")
    target_end = datetime.strptime(args.target_end, "%Y-%m-%d")
    if target_end <= target_start:
        raise ValueError("--target-end must be later than --target-start")

    build_recent_dataset(args.src, args.dst, target_start, target_end)
    print(f"Recent dataset written to: {args.dst}")


if __name__ == "__main__":
    main()
