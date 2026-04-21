from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ASSISTANT_LINE_RE = re.compile(r"^(assistant(?:\s+\([^)]+\))?:\s*)(.*)$")


@dataclass
class Edit:
    file: Path
    session_key: str
    before: str
    after: str


def _cleanup_spacing(text: str) -> str:
    text = re.sub(r"\s+([,!.?;:])", r"\1", text)
    text = re.sub(r"([,])([!?])", r"\2", text)
    text = re.sub(r"\s{2,}", " ", text)
    text = re.sub(r"^\s*,\s*", "", text)
    text = re.sub(r"\s+,", ",", text)
    text = re.sub(r"\s+([.!?])", r"\1", text)
    return text.strip()


def _remove_vocative_once(text: str, name: str, keep_first: bool) -> tuple[str, bool, bool]:
    """Remove repeated assistant vocative mentions of the user name.

    Returns: (new_text, found_name, kept_name)
    """
    escaped = re.escape(name)
    name_re = re.compile(rf"\b{escaped}\b")
    first_match = name_re.search(text)
    if not first_match:
        return text, False, False

    kept_name = False
    prefix = ""
    work = text
    if keep_first:
        kept_name = True
        prefix = text[: first_match.end()]
        work = text[first_match.end() :]

    patterns: list[tuple[re.Pattern[str], str]] = [
        # "Thanks, Caroline, for..." -> "Thanks for..."
        (
            re.compile(rf"\b(Thanks|Thank you),\s*{escaped},\s+", re.IGNORECASE),
            r"\1 ",
        ),
        # "Wow, Caroline, you're..." -> "Wow, you're..."
        (re.compile(rf",\s*{escaped},\s*", re.IGNORECASE), ", "),
        # "Wow, Caroline!" / "Yep, Caroline." -> "Wow!" / "Yep."
        (re.compile(rf",\s*{escaped}\s*([.!?])", re.IGNORECASE), r"\1"),
        # "Thanks Caroline!" / "Congrats Caroline!" -> "Thanks!" / "Congrats!"
        (
            re.compile(
                rf"\b(Hey|Hi|Hello|Wow|Thanks|Thank you|Congrats|Congratulations|Yep|Yeah|Yes|Okay|Ok|Absolutely)\s+{escaped}\s*([,.!?])",
                re.IGNORECASE,
            ),
            r"\1\2",
        ),
        # "Caroline, ..." at the beginning of the remaining assistant text.
        (re.compile(rf"^\s*{escaped}\s*,\s*", re.IGNORECASE), ""),
        # "Caroline!" / "Caroline." as a standalone sentence fragment.
        (re.compile(rf"^\s*{escaped}\s*([.!?])\s*", re.IGNORECASE), ""),
        # "... Caroline!" preceded by whitespace after an interjection without comma.
        (re.compile(rf"\s+{escaped}\s*([.!?])", re.IGNORECASE), r"\1"),
    ]

    changed = False
    for pattern, replacement in patterns:
        work, count = pattern.subn(replacement, work)
        changed = changed or count > 0

    if keep_first:
        # If the first kept mention is followed by a removed comma fragment, normalize gently.
        new_text = prefix + work
    else:
        # Remove a leading name if the whole assistant reply starts with a vocative.
        work = re.sub(rf"^\s*{escaped}\s*([,.!?])\s*", "", work, flags=re.IGNORECASE)
        new_text = work

    if changed or not keep_first:
        new_text = _cleanup_spacing(new_text)

    return new_text, True, kept_name


def trim_content(content: str, user_name: str, has_kept_first: bool) -> tuple[str, bool, list[tuple[str, str]]]:
    changed_lines: list[tuple[str, str]] = []
    output_lines: list[str] = []

    for line in content.splitlines():
        match = ASSISTANT_LINE_RE.match(line)
        if not match:
            output_lines.append(line)
            continue

        speaker_prefix, body = match.groups()
        new_body, found_name, kept_name = _remove_vocative_once(
            body,
            user_name,
            keep_first=not has_kept_first,
        )
        if found_name and kept_name:
            has_kept_first = True

        new_line = f"{speaker_prefix}{new_body}"
        if new_line != line:
            changed_lines.append((line, new_line))
        output_lines.append(new_line)

    return "\n".join(output_lines), has_kept_first, changed_lines


def process_converted_file(path: Path) -> tuple[dict[str, Any], list[Edit]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    user_name = data.get("user_character") or data.get("speaker_a") or ""
    if not user_name:
        return data, []

    edits: list[Edit] = []
    has_kept_first = False
    for session in data.get("sessions", []):
        content = session.get("content", "")
        new_content, has_kept_first, changed_lines = trim_content(
            content,
            user_name,
            has_kept_first,
        )
        if new_content != content:
            session["content"] = new_content
            for before, after in changed_lines:
                edits.append(
                    Edit(
                        file=path,
                        session_key=session.get("session_key", ""),
                        before=before,
                        after=after,
                    )
                )

    return data, edits


def iter_converted_files(src: Path) -> list[Path]:
    return sorted(src.glob("sample_*_*_converted.json"))


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(
        description="Trim repeated assistant vocative mentions of the user name in converted datasets.",
    )
    parser.add_argument("--src", type=Path, required=True, help="Source converted data directory")
    parser.add_argument("--dst", type=Path, required=True, help="Destination directory")
    parser.add_argument("--write", action="store_true", help="Write the cleaned dataset to --dst")
    parser.add_argument("--max-preview", type=int, default=80, help="Maximum changed lines to preview")
    args = parser.parse_args()

    src = args.src
    dst = args.dst
    if not src.exists():
        raise SystemExit(f"Source directory does not exist: {src}")

    all_edits: list[Edit] = []
    converted_payloads: dict[Path, dict[str, Any]] = {}
    for path in iter_converted_files(src):
        payload, edits = process_converted_file(path)
        converted_payloads[path] = payload
        all_edits.extend(edits)

    print(f"Source: {src}")
    print(f"Destination: {dst}")
    print(f"Converted files scanned: {len(converted_payloads)}")
    print(f"Assistant lines changed: {len(all_edits)}")

    for edit in all_edits[: args.max_preview]:
        print("\n---")
        print(f"{edit.file.name} / {edit.session_key}")
        print(f"- {edit.before}")
        print(f"+ {edit.after}")

    if len(all_edits) > args.max_preview:
        print(f"\n... {len(all_edits) - args.max_preview} more changed lines omitted")

    if not args.write:
        print("\nDry run only. Re-run with --write to create the destination dataset.")
        return

    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)

    for src_path, payload in converted_payloads.items():
        rel = src_path.relative_to(src)
        out_path = dst / rel
        out_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    print(f"\nWrote cleaned dataset to: {dst}")


if __name__ == "__main__":
    main()
