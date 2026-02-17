from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from .errors import DSLRuntimeError, DSLSyntaxError
from .interpreter import run_script
from .semantic import PrepareStats, prepare_semantic_database


def build_run_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run FilesDSL scripts.")
    parser.add_argument("script", help="Path to the .fdsl script")
    parser.add_argument(
        "--sandbox-root",
        default=None,
        help="Optional path limit. Defaults to the script directory.",
    )
    return parser


def build_prepare_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prepare semantic index for a folder.")
    parser.add_argument("folder", help="Folder to index recursively")
    return parser


def _display_path(path: Path, cwd: Path) -> str:
    try:
        return Path(os.path.relpath(path.resolve(), cwd.resolve())).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _run_script_command(argv: list[str]) -> int:
    parser = build_run_parser()
    args = parser.parse_args(argv)

    cwd_for_display = Path.cwd().resolve()
    script_path = Path(args.script)
    if not script_path.exists():
        print(f"Error: script not found: {_display_path(script_path, cwd_for_display)}", file=sys.stderr)
        return 2
    if not script_path.is_file():
        print(
            f"Error: script is not a file: {_display_path(script_path, cwd_for_display)}",
            file=sys.stderr,
        )
        return 2

    source = script_path.read_text(encoding="utf-8")
    cwd = script_path.parent.resolve()
    sandbox_root = Path(args.sandbox_root).resolve() if args.sandbox_root else Path.cwd().resolve()

    try:
        run_script(source, cwd=cwd, sandbox_root=sandbox_root)
        return 0
    except DSLSyntaxError as exc:
        print(exc.format(), file=sys.stderr)
        return 1
    except DSLRuntimeError as exc:
        print(exc.format(), file=sys.stderr)
        return 1


def _prepare_command(argv: list[str]) -> int:
    parser = build_prepare_parser()
    args = parser.parse_args(argv)

    cwd = Path.cwd().resolve()
    folder_path = Path(args.folder)
    if not folder_path.is_absolute():
        folder_path = (cwd / folder_path).resolve()
    else:
        folder_path = folder_path.resolve()

    try:
        stats = prepare_semantic_database(folder_path)
    except DSLRuntimeError as exc:
        print(exc.format(), file=sys.stderr)
        return 1

    _print_prepare_summary(stats, cwd)
    return 0


def _print_prepare_summary(stats: PrepareStats, cwd: Path) -> None:
    print(f"Prepared semantic index for {_display_path(stats.folder, cwd)}")
    print(f"Database: {_display_path(stats.db_path, cwd)}")
    print(f"Indexed files: {stats.indexed_files}")
    print(f"Indexed pages: {stats.indexed_pages}")


def main(argv: list[str] | None = None) -> int:
    args = list(argv) if argv is not None else sys.argv[1:]
    if args and args[0] == "prepare":
        return _prepare_command(args[1:])
    return _run_script_command(args)


if __name__ == "__main__":
    raise SystemExit(main())
