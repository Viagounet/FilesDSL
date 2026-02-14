from __future__ import annotations

from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from typing import Any

from .ast_nodes import (
    Assign,
    Attribute,
    BinaryOp,
    Call,
    CompareOp,
    ExprStatement,
    ForStatement,
    IfStatement,
    ListLiteral,
    Literal,
    Name,
    Program,
    RangeItem,
    Statement,
    UnaryOp,
)
from .errors import DSLRuntimeError, SourceLocation
from .parser import Parser
from .runtime import DSLDirectory


class Interpreter:
    def __init__(
        self,
        source: str,
        *,
        cwd: Path | None = None,
        sandbox_root: Path | None = None,
    ) -> None:
        self.source = source
        self.source_lines = source.splitlines()
        self.cwd = (cwd or Path.cwd()).resolve()
        self.sandbox_root = (sandbox_root or self.cwd).resolve()
        self.variables: dict[str, Any] = {}
        self.builtins = {
            "Directory": self._builtin_directory,
            "print": self._builtin_print,
            "len": len,
        }

    def run(self) -> dict[str, Any]:
        program = Parser(self.source).parse()
        self._execute_program(program)
        return self.variables

    def _execute_program(self, program: Program) -> None:
        for statement in program.statements:
            self._execute_statement(statement)

    def _execute_statement(self, stmt: Statement) -> None:
        try:
            if isinstance(stmt, Assign):
                self.variables[stmt.name] = self._eval_expr(stmt.expr)
                return

            if isinstance(stmt, ExprStatement):
                self._eval_expr(stmt.expr)
                return

            if isinstance(stmt, ForStatement):
                iterable = self._eval_expr(stmt.iterable)
                if not hasattr(iterable, "__iter__"):
                    self._runtime_error("for-loop target is not iterable", stmt.loc)
                for value in iterable:
                    self.variables[stmt.var_name] = value
                    for child_stmt in stmt.body:
                        self._execute_statement(child_stmt)
                return

            if isinstance(stmt, IfStatement):
                for condition, body in stmt.branches:
                    if self._is_truthy(self._eval_expr(condition)):
                        for child_stmt in body:
                            self._execute_statement(child_stmt)
                        return
                if stmt.else_body is not None:
                    for child_stmt in stmt.else_body:
                        self._execute_statement(child_stmt)
                return

            self._runtime_error("Unsupported statement", stmt.loc)
        except DSLRuntimeError:
            raise
        except Exception as exc:  # pragma: no cover
            self._runtime_error(str(exc), stmt.loc)

    def _eval_expr(self, expr):
        if isinstance(expr, Literal):
            return expr.value

        if isinstance(expr, Name):
            if expr.identifier in self.variables:
                return self.variables[expr.identifier]
            if expr.identifier in self.builtins:
                return self.builtins[expr.identifier]
            self._runtime_error(f"Undefined variable '{expr.identifier}'", expr.loc)

        if isinstance(expr, ListLiteral):
            return self._eval_list_literal(expr)

        if isinstance(expr, RangeItem):
            self._runtime_error("Range syntax is only valid inside list literals", expr.loc)

        if isinstance(expr, Attribute):
            obj = self._eval_expr(expr.obj)
            if not hasattr(obj, expr.name):
                self._runtime_error(
                    f"Object of type '{type(obj).__name__}' has no attribute '{expr.name}'",
                    expr.loc,
                )
            return getattr(obj, expr.name)

        if isinstance(expr, Call):
            callee = self._eval_expr(expr.callee)
            if not callable(callee):
                self._runtime_error("Attempted to call a non-callable value", expr.loc)

            args = [self._eval_expr(arg) for arg in expr.args]
            kwargs = {name: self._eval_expr(value) for name, value in expr.kwargs}
            try:
                return callee(*args, **kwargs)
            except TypeError as exc:
                self._runtime_error(f"Call failed: {exc}", expr.loc)
            except DSLRuntimeError:
                raise
            except Exception as exc:  # pragma: no cover
                self._runtime_error(str(exc), expr.loc)

        if isinstance(expr, UnaryOp):
            operand = self._eval_expr(expr.operand)
            if expr.op == "not":
                return not self._is_truthy(operand)
            if expr.op == "-":
                if not isinstance(operand, int):
                    self._runtime_error("Unary '-' expects an integer", expr.loc)
                return -operand
            self._runtime_error(f"Unsupported unary operator '{expr.op}'", expr.loc)

        if isinstance(expr, BinaryOp):
            if expr.op == "and":
                return self._is_truthy(self._eval_expr(expr.left)) and self._is_truthy(
                    self._eval_expr(expr.right)
                )
            if expr.op == "or":
                return self._is_truthy(self._eval_expr(expr.left)) or self._is_truthy(
                    self._eval_expr(expr.right)
                )

            left = self._eval_expr(expr.left)
            right = self._eval_expr(expr.right)
            if expr.op == "+":
                return left + right
            if expr.op == "-":
                return left - right
            if expr.op == "*":
                return left * right
            if expr.op == "/":
                return left / right
            if expr.op == "%":
                return left % right
            self._runtime_error(f"Unsupported binary operator '{expr.op}'", expr.loc)

        if isinstance(expr, CompareOp):
            left = self._eval_expr(expr.left)
            right = self._eval_expr(expr.right)
            if expr.op == "==":
                return left == right
            if expr.op == "!=":
                return left != right
            if expr.op == "<":
                return left < right
            if expr.op == "<=":
                return left <= right
            if expr.op == ">":
                return left > right
            if expr.op == ">=":
                return left >= right
            self._runtime_error(f"Unsupported comparison operator '{expr.op}'", expr.loc)

        self._runtime_error("Unsupported expression", expr.loc)

    def _eval_list_literal(self, node: ListLiteral) -> list[Any]:
        values: list[Any] = []
        for item in node.items:
            if isinstance(item, RangeItem):
                start = self._eval_expr(item.start)
                end = self._eval_expr(item.end)
                if not isinstance(start, int) or not isinstance(end, int):
                    self._runtime_error("Range bounds must be integers", item.loc)
                if start <= end:
                    values.extend(range(start, end + 1))
                else:
                    values.extend(range(start, end - 1, -1))
                continue
            values.append(self._eval_expr(item))
        return values

    def _builtin_directory(self, path: str, recursive: bool = True):
        if not isinstance(path, str):
            raise DSLRuntimeError("Directory(path) expects a string path")
        if not isinstance(recursive, bool):
            raise DSLRuntimeError("Directory(..., recursive=...) expects a boolean")

        candidate = Path(path)
        if not candidate.is_absolute():
            candidate = (self.cwd / candidate).resolve()
        else:
            candidate = candidate.resolve()

        if not candidate.is_relative_to(self.sandbox_root):
            raise DSLRuntimeError(
                f"Access denied. '{candidate.as_posix()}' is outside sandbox root "
                f"'{self.sandbox_root.as_posix()}'"
            )

        return DSLDirectory(candidate, recursive=recursive)

    def _builtin_print(self, *args) -> None:
        rendered = [self._render_value(arg) for arg in args]
        print(*rendered)

    def _render_value(self, value: Any) -> Any:
        if isinstance(value, list):
            return [self._render_value(item) for item in value]
        return value

    def _is_truthy(self, value: Any) -> bool:
        return bool(value)

    def _runtime_error(self, message: str, loc: SourceLocation | None = None) -> None:
        if loc is None:
            raise DSLRuntimeError(message)
        source_line = ""
        if 1 <= loc.line <= len(self.source_lines):
            source_line = self.source_lines[loc.line - 1]
        raise DSLRuntimeError(
            message=message,
            line=loc.line,
            column=loc.column,
            source_line=source_line,
        )


def run_script(
    source: str,
    *,
    cwd: Path | None = None,
    sandbox_root: Path | None = None,
) -> dict[str, Any]:
    interpreter = Interpreter(source, cwd=cwd, sandbox_root=sandbox_root)
    return interpreter.run()


def execute_fdsl(
    code: str,
    *,
    cwd: str | Path | None = None,
    sandbox_root: str | Path | None = None,
) -> str:
    """Execute FDSL code provided as a Python string.

    Args:
        code: FDSL source code to execute.
        cwd: Base directory used to resolve relative paths in Directory(...).
        sandbox_root: Path boundary for directory access. Defaults to cwd.

    Returns:
        The execution history captured from stdout (console prints).
    """
    resolved_cwd = Path(cwd).resolve() if cwd is not None else None
    resolved_sandbox = Path(sandbox_root).resolve() if sandbox_root is not None else None
    output = StringIO()
    with redirect_stdout(output):
        run_script(code, cwd=resolved_cwd, sandbox_root=resolved_sandbox)
    return output.getvalue()
