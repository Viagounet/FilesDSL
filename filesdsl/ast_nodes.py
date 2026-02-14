from __future__ import annotations

from dataclasses import dataclass
from typing import Union

from .errors import SourceLocation


@dataclass
class Program:
    statements: list["Statement"]


class Statement:
    loc: SourceLocation


class Expression:
    loc: SourceLocation


@dataclass
class Assign(Statement):
    name: str
    expr: Expression
    loc: SourceLocation


@dataclass
class ExprStatement(Statement):
    expr: Expression
    loc: SourceLocation


@dataclass
class ForStatement(Statement):
    var_name: str
    iterable: Expression
    body: list[Statement]
    loc: SourceLocation


@dataclass
class IfStatement(Statement):
    branches: list[tuple[Expression, list[Statement]]]
    else_body: list[Statement] | None
    loc: SourceLocation


@dataclass
class Literal(Expression):
    value: object
    loc: SourceLocation


@dataclass
class Name(Expression):
    identifier: str
    loc: SourceLocation


@dataclass
class RangeItem(Expression):
    start: Expression
    end: Expression
    loc: SourceLocation


ListItem = Union[Expression, RangeItem]


@dataclass
class ListLiteral(Expression):
    items: list[ListItem]
    loc: SourceLocation


@dataclass
class Attribute(Expression):
    obj: Expression
    name: str
    loc: SourceLocation


@dataclass
class Call(Expression):
    callee: Expression
    args: list[Expression]
    kwargs: list[tuple[str, Expression]]
    loc: SourceLocation


@dataclass
class UnaryOp(Expression):
    op: str
    operand: Expression
    loc: SourceLocation


@dataclass
class BinaryOp(Expression):
    op: str
    left: Expression
    right: Expression
    loc: SourceLocation


@dataclass
class CompareOp(Expression):
    op: str
    left: Expression
    right: Expression
    loc: SourceLocation
