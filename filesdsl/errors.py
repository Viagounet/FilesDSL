from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SourceLocation:
    line: int
    column: int


class DSLBaseError(Exception):
    """Base class for FilesDSL errors."""


class DSLSyntaxError(DSLBaseError):
    def __init__(self, message: str, line: int, column: int, source_line: str) -> None:
        super().__init__(message)
        self.message = message
        self.line = line
        self.column = column
        self.source_line = source_line

    def format(self) -> str:
        pointer = " " * max(self.column - 1, 0) + "^"
        return (
            f"SyntaxError: {self.message}\n"
            f"  at line {self.line}, column {self.column}\n"
            f"    {self.source_line}\n"
            f"    {pointer}"
        )


class DSLRuntimeError(DSLBaseError):
    def __init__(
        self,
        message: str,
        line: int | None = None,
        column: int | None = None,
        source_line: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.line = line
        self.column = column
        self.source_line = source_line

    def format(self) -> str:
        if self.line is None or self.column is None or self.source_line is None:
            return f"RuntimeError: {self.message}"
        pointer = " " * max(self.column - 1, 0) + "^"
        return (
            f"RuntimeError: {self.message}\n"
            f"  at line {self.line}, column {self.column}\n"
            f"    {self.source_line}\n"
            f"    {pointer}"
        )


class DSLTimeoutError(DSLRuntimeError):
    def __init__(
        self,
        message: str,
        *,
        elapsed_s: float,
        phase: str,
        partial_output: str | None = None,
    ) -> None:
        super().__init__(message)
        self.elapsed_s = elapsed_s
        self.phase = phase
        self.partial_output = partial_output
