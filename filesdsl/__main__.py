from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .errors import DSLRuntimeError, DSLSyntaxError
from .interpreter import run_script


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run FilesDSL scripts.")
    parser.add_argument("script", help="Path to the .fdsl script")
    parser.add_argument(
        "--sandbox-root",
        default=None,
        help="Optional path limit. Defaults to the script directory.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    script_path = Path(args.script)
    if not script_path.exists():
        print(f"Error: script not found: {script_path.as_posix()}", file=sys.stderr)
        return 2
    if not script_path.is_file():
        print(f"Error: script is not a file: {script_path.as_posix()}", file=sys.stderr)
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


if __name__ == "__main__":
    raise SystemExit(main())
