"""Codex PreToolUse command policy for ponkan-python."""

import json
import re
import sys
from collections.abc import Iterable, Mapping, Sequence
from typing import Final

FORBIDDEN_COMMANDS: Final[tuple[str, ...]] = (
    "python",
    "python3",
    "py",
    "pip",
    "pip3",
    "pytest",
    "ruff",
    "ty",
)

FORBIDDEN_DIRECT_COMMAND_PATTERN: Final = re.compile(
    r"(?i)(^|[;&|]\s*)("
    + "|".join(re.escape(command) for command in FORBIDDEN_COMMANDS)
    + r")(\s|$)"
)
DESTRUCTIVE_GIT_PATTERNS: Final[tuple[re.Pattern[str], ...]] = (
    re.compile(r"(?i)(^|[;&|]\s*)git\s+reset\s+--hard(\s|$)"),
    re.compile(r"(?i)(^|[;&|]\s*)git\s+clean(\s|$)"),
    re.compile(r"(?i)(^|[;&|]\s*)git\s+checkout\s+--(\s|$)"),
)


def iter_strings(value: object) -> Iterable[str]:
    if isinstance(value, str):
        yield value
        return

    if isinstance(value, Mapping):
        for child in value.values():
            yield from iter_strings(child)
        return

    if isinstance(value, Sequence):
        for child in value:
            yield from iter_strings(child)


def violation_for_text(text: str) -> str | None:
    direct_match = FORBIDDEN_DIRECT_COMMAND_PATTERN.search(text)
    if direct_match is not None:
        command = direct_match.group(2)
        return f"use `uv run {command} ...` or the matching `uv` subcommand instead of `{command}`"

    for pattern in DESTRUCTIVE_GIT_PATTERNS:
        if pattern.search(text) is not None:
            return "destructive git commands require explicit user direction outside Codex hooks"

    return None


def load_payload(raw_input: str) -> object:
    if raw_input.strip() == "":
        return {}
    try:
        payload: object = json.loads(raw_input)
    except json.JSONDecodeError:
        return raw_input
    else:
        return payload


def main() -> int:
    payload = load_payload(sys.stdin.read())
    for text in iter_strings(payload):
        violation = violation_for_text(text)
        if violation is not None:
            sys.stderr.write(f"Blocked by ponkan-python Codex policy: {violation}\n")
            return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
