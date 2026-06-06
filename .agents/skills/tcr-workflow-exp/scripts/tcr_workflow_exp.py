"""Safe experimental harness for test && commit || revert."""

import argparse
import re
import shutil
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Final

WORKTREE_ROOT: Final = Path(".worktrees") / "tcr-workflow-exp"
DEFAULT_BASE: Final = "HEAD"
DEFAULT_MESSAGE: Final = "test: TCR checkpoint"
NAME_PATTERN: Final = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


class TcrError(RuntimeError):
    """User-facing TCR harness error."""


def write_stdout(message: str) -> None:
    """Write a line to stdout."""
    sys.stdout.write(f"{message}\n")


def write_stderr(message: str) -> None:
    """Write a line to stderr."""
    sys.stderr.write(f"{message}\n")


def resolve_executable(name: str, *, cwd: Path) -> str:
    """Resolve an executable from PATH or a path relative to cwd."""
    if any(separator in name for separator in ("/", "\\")):
        candidate = Path(name)
        if not candidate.is_absolute():
            candidate = cwd / candidate
        return str(candidate.resolve())

    resolved = shutil.which(name)
    if resolved is None:
        message = f"Executable not found on PATH: {name}"
        raise TcrError(message)
    return resolved


def run_command(
    command: Sequence[str],
    *,
    cwd: Path,
    capture: bool = False,
) -> subprocess.CompletedProcess[str]:
    """Run a command without shell expansion."""
    if not command:
        message = "Command must not be empty"
        raise TcrError(message)

    executable = resolve_executable(command[0], cwd=cwd)
    return subprocess.run(  # noqa: S603
        [executable, *command[1:]],
        cwd=cwd,
        text=True,
        capture_output=capture,
        check=False,
    )


def run_git(
    args: Sequence[str],
    *,
    cwd: Path,
    capture: bool = False,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    """Run git with explicit arguments."""
    result = run_command(["git", *args], cwd=cwd, capture=capture)
    if check and result.returncode != 0:
        details = result.stderr.strip() if result.stderr else "no stderr"
        message = f"git {' '.join(args)} failed: {details}"
        raise TcrError(message)
    return result


def resolve_repo_root() -> Path:
    """Resolve the repository root for the current process."""
    result = run_git(["rev-parse", "--show-toplevel"], cwd=Path.cwd(), capture=True)
    return Path(result.stdout.strip()).resolve()


def safe_worktree_root(repo_root: Path) -> Path:
    """Return the only directory where this harness may discard changes."""
    return (repo_root / WORKTREE_ROOT).resolve()


def validate_name(name: str) -> None:
    """Validate a worktree name used for default path and branch values."""
    if NAME_PATTERN.fullmatch(name) is None:
        message = (
            "Name must start with an alphanumeric character and contain only "
            "alphanumerics, dot, underscore, or hyphen"
        )
        raise TcrError(message)


def resolve_safe_worktree(repo_root: Path, worktree: str | None, name: str | None = None) -> Path:
    """Resolve and validate a TCR worktree path."""
    if worktree is None:
        if name is None:
            message = "Either --worktree or --name is required"
            raise TcrError(message)
        validate_name(name)
        candidate = repo_root / WORKTREE_ROOT / name
    else:
        candidate_path = Path(worktree)
        candidate = candidate_path if candidate_path.is_absolute() else repo_root / candidate_path

    resolved = candidate.resolve()
    allowed_root = safe_worktree_root(repo_root)
    try:
        resolved.relative_to(allowed_root)
    except ValueError as exc:
        message = f"Unsafe worktree path outside {allowed_root}: {resolved}"
        raise TcrError(message) from exc
    return resolved


def ensure_git_worktree(path: Path) -> None:
    """Ensure a path exists and is a git worktree."""
    if not path.exists():
        message = f"Worktree does not exist: {path}"
        raise TcrError(message)

    result = run_git(["rev-parse", "--is-inside-work-tree"], cwd=path, capture=True)
    if result.stdout.strip() != "true":
        message = f"Path is not a git worktree: {path}"
        raise TcrError(message)


def strip_command_separator(command: Sequence[str]) -> list[str]:
    """Remove the argparse `--` separator from a remainder command."""
    command_list = list(command)
    if command_list and command_list[0] == "--":
        return command_list[1:]
    return command_list


def status_porcelain(worktree: Path) -> str:
    """Return porcelain status for a worktree."""
    result = run_git(["status", "--porcelain"], cwd=worktree, capture=True)
    return result.stdout


def command_init(args: argparse.Namespace) -> int:
    """Create an isolated TCR worktree."""
    repo_root = resolve_repo_root()
    validate_name(args.name)
    worktree = resolve_safe_worktree(repo_root, args.worktree, args.name)
    if worktree.exists():
        message = f"Worktree already exists: {worktree}"
        raise TcrError(message)

    branch = args.branch or f"tcr-workflow-exp/{args.name}"
    worktree.parent.mkdir(parents=True, exist_ok=True)
    run_git(["worktree", "add", "-b", branch, str(worktree), args.base], cwd=repo_root)
    write_stdout(f"Created TCR worktree: {worktree}")
    write_stdout(f"Branch: {branch}")
    return 0


def command_status(args: argparse.Namespace) -> int:
    """Show status for an isolated TCR worktree."""
    repo_root = resolve_repo_root()
    worktree = resolve_safe_worktree(repo_root, args.worktree)
    ensure_git_worktree(worktree)
    branch = run_git(["branch", "--show-current"], cwd=worktree, capture=True).stdout.strip()
    write_stdout(f"Worktree: {worktree}")
    write_stdout(f"Branch: {branch}")
    status = status_porcelain(worktree).strip()
    write_stdout("Status:")
    write_stdout(status or "clean")
    return 0


def commit_if_needed(worktree: Path, message: str) -> int:
    """Commit current worktree changes when there is anything to commit."""
    if not status_porcelain(worktree).strip():
        write_stdout("Tests passed; no changes to commit.")
        return 0

    run_git(["add", "-A"], cwd=worktree)
    run_git(["commit", "-m", message], cwd=worktree)
    write_stdout("Tests passed; checkpoint committed.")
    return 0


def discard_worktree_changes(worktree: Path, *, keep_untracked: bool) -> None:
    """Discard failed TCR increment inside the isolated worktree."""
    run_git(["reset", "--hard", "HEAD"], cwd=worktree)
    if not keep_untracked:
        run_git(["clean", "-fd"], cwd=worktree)


def command_cycle(args: argparse.Namespace) -> int:
    """Run one TCR cycle in an isolated worktree."""
    repo_root = resolve_repo_root()
    worktree = resolve_safe_worktree(repo_root, args.worktree)
    ensure_git_worktree(worktree)
    test_command = strip_command_separator(args.test_command)
    if not test_command:
        message = "A test command is required after --"
        raise TcrError(message)

    result = run_command(test_command, cwd=worktree)
    if result.returncode == 0:
        return commit_if_needed(worktree, args.message)

    discard_worktree_changes(worktree, keep_untracked=args.keep_untracked)
    write_stderr("Tests failed; isolated worktree changes were discarded.")
    return result.returncode


def build_parser() -> argparse.ArgumentParser:
    """Build the command line parser."""
    parser = argparse.ArgumentParser(
        description="Safe experimental TCR harness for isolated git worktrees."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    init = subparsers.add_parser(
        "init",
        help="create a TCR worktree under .worktrees/tcr-workflow-exp",
    )
    init.add_argument("--name", required=True, help="short experiment name")
    init.add_argument(
        "--worktree",
        help="explicit worktree path under .worktrees/tcr-workflow-exp",
    )
    init.add_argument("--branch", help="branch name; defaults to tcr-workflow-exp/{name}")
    init.add_argument("--base", default=DEFAULT_BASE, help="base commit or branch")
    init.set_defaults(handler=command_init)

    status = subparsers.add_parser("status", help="show isolated worktree status")
    status.add_argument(
        "--worktree",
        required=True,
        help="worktree path under .worktrees/tcr-workflow-exp",
    )
    status.set_defaults(handler=command_status)

    cycle = subparsers.add_parser(
        "cycle",
        help="run test && commit || discard in an isolated worktree",
    )
    cycle.add_argument(
        "--worktree",
        required=True,
        help="worktree path under .worktrees/tcr-workflow-exp",
    )
    cycle.add_argument("--message", default=DEFAULT_MESSAGE, help="checkpoint commit message")
    cycle.add_argument(
        "--keep-untracked",
        action="store_true",
        help="keep untracked files when tests fail",
    )
    cycle.add_argument("test_command", nargs=argparse.REMAINDER, help="test command after --")
    cycle.set_defaults(handler=command_cycle)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the TCR harness CLI."""
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.handler(args))
    except TcrError as exc:
        write_stderr(f"error: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
