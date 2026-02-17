from __future__ import annotations

import re
from dataclasses import dataclass

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
from .errors import DSLSyntaxError, SourceLocation


_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_FOR_RE = re.compile(r"^for\s+([A-Za-z_][A-Za-z0-9_]*)\s+in\s+(.+):\s*$")
_IF_RE = re.compile(r"^if\s+(.+):\s*$")
_ELIF_RE = re.compile(r"^elif\s+(.+):\s*$")


@dataclass
class Token:
    kind: str
    value: str
    column: int


class ExpressionLexer:
    def __init__(self, text: str, base_column: int, line: int, source_line: str) -> None:
        self.text = text
        self.base_column = base_column
        self.line = line
        self.source_line = source_line
        self.index = 0

    def _error(self, message: str, column: int) -> DSLSyntaxError:
        return DSLSyntaxError(message, self.line, self.base_column + column, self.source_line)

    def tokenize(self) -> list[Token]:
        tokens: list[Token] = []
        while self.index < len(self.text):
            char = self.text[self.index]
            if char.isspace():
                self.index += 1
                continue

            start = self.index
            two_char = self.text[self.index : self.index + 2]
            if two_char in {"==", "!=", "<=", ">="}:
                mapping = {
                    "==": "EQEQ",
                    "!=": "NEQ",
                    "<=": "LTE",
                    ">=": "GTE",
                }
                tokens.append(Token(mapping[two_char], two_char, start))
                self.index += 2
                continue

            if char in "+-*/%()[],.:=<>":
                mapping = {
                    "+": "PLUS",
                    "-": "MINUS",
                    "*": "STAR",
                    "/": "SLASH",
                    "%": "PERCENT",
                    "(": "LPAREN",
                    ")": "RPAREN",
                    "[": "LBRACK",
                    "]": "RBRACK",
                    ",": "COMMA",
                    ".": "DOT",
                    ":": "COLON",
                    "=": "EQ",
                    "<": "LT",
                    ">": "GT",
                }
                tokens.append(Token(mapping[char], char, start))
                self.index += 1
                continue

            if char.isdigit():
                self.index += 1
                while self.index < len(self.text) and self.text[self.index].isdigit():
                    self.index += 1
                value = self.text[start : self.index]
                tokens.append(Token("NUMBER", value, start))
                continue

            if char in {"'", '"'}:
                tokens.append(self._read_string())
                continue

            if char.isalpha() or char == "_":
                self.index += 1
                while self.index < len(self.text):
                    ch = self.text[self.index]
                    if ch.isalnum() or ch == "_":
                        self.index += 1
                        continue
                    break
                value = self.text[start : self.index]
                keyword_map = {
                    "and": "AND",
                    "or": "OR",
                    "not": "NOT",
                    "True": "TRUE",
                    "False": "FALSE",
                    "true": "TRUE",
                    "false": "FALSE",
                }
                kind = keyword_map.get(value, "NAME")
                tokens.append(Token(kind, value, start))
                continue

            raise self._error(f"Unexpected character '{char}'", start)

        tokens.append(Token("EOF", "", len(self.text)))
        return tokens

    def _read_string(self) -> Token:
        quote = self.text[self.index]
        start = self.index
        self.index += 1
        output: list[str] = []
        while self.index < len(self.text):
            char = self.text[self.index]
            if char == quote:
                self.index += 1
                return Token("STRING", "".join(output), start)
            if char == "\\":
                if self.index + 1 >= len(self.text):
                    raise self._error("Unterminated escape in string literal", start)
                escaped = self.text[self.index + 1]
                escape_map = {
                    "n": "\n",
                    "t": "\t",
                    "r": "\r",
                    "\\": "\\",
                    "'": "'",
                    '"': '"',
                }
                output.append(escape_map.get(escaped, escaped))
                self.index += 2
                continue
            output.append(char)
            self.index += 1
        raise self._error("Unterminated string literal", start)


class ExpressionParser:
    def __init__(self, tokens: list[Token], line: int, source_line: str, base_column: int) -> None:
        self.tokens = tokens
        self.line = line
        self.source_line = source_line
        self.base_column = base_column
        self.index = 0

    def parse(self):
        expr = self._parse_or()
        if self._current().kind != "EOF":
            token = self._current()
            self._error(f"Unexpected token '{token.value or token.kind}'", token)
        return expr

    def _current(self) -> Token:
        return self.tokens[self.index]

    def _peek(self, n: int = 1) -> Token:
        idx = self.index + n
        if idx >= len(self.tokens):
            return self.tokens[-1]
        return self.tokens[idx]

    def _advance(self) -> Token:
        token = self.tokens[self.index]
        self.index += 1
        return token

    def _match(self, *kinds: str) -> Token | None:
        token = self._current()
        if token.kind in kinds:
            self.index += 1
            return token
        return None

    def _expect(self, kind: str, message: str) -> Token:
        token = self._current()
        if token.kind != kind:
            self._error(message, token)
        self.index += 1
        return token

    def _error(self, message: str, token: Token) -> None:
        raise DSLSyntaxError(
            message,
            self.line,
            self.base_column + token.column,
            self.source_line,
        )

    def _loc(self, token: Token) -> SourceLocation:
        return SourceLocation(self.line, self.base_column + token.column)

    def _parse_or(self):
        expr = self._parse_and()
        while token := self._match("OR"):
            right = self._parse_and()
            expr = BinaryOp("or", expr, right, self._loc(token))
        return expr

    def _parse_and(self):
        expr = self._parse_not()
        while token := self._match("AND"):
            right = self._parse_not()
            expr = BinaryOp("and", expr, right, self._loc(token))
        return expr

    def _parse_not(self):
        if token := self._match("NOT"):
            operand = self._parse_not()
            return UnaryOp("not", operand, self._loc(token))
        return self._parse_compare()

    def _parse_compare(self):
        expr = self._parse_add()
        while True:
            token = self._match("EQEQ", "NEQ", "LT", "LTE", "GT", "GTE")
            if token is None:
                break
            op_map = {
                "EQEQ": "==",
                "NEQ": "!=",
                "LT": "<",
                "LTE": "<=",
                "GT": ">",
                "GTE": ">=",
            }
            right = self._parse_add()
            expr = CompareOp(op_map[token.kind], expr, right, self._loc(token))
        return expr

    def _parse_add(self):
        expr = self._parse_mul()
        while True:
            token = self._match("PLUS", "MINUS")
            if token is None:
                break
            op = "+" if token.kind == "PLUS" else "-"
            right = self._parse_mul()
            expr = BinaryOp(op, expr, right, self._loc(token))
        return expr

    def _parse_mul(self):
        expr = self._parse_unary()
        while True:
            token = self._match("STAR", "SLASH", "PERCENT")
            if token is None:
                break
            op_map = {"STAR": "*", "SLASH": "/", "PERCENT": "%"}
            right = self._parse_unary()
            expr = BinaryOp(op_map[token.kind], expr, right, self._loc(token))
        return expr

    def _parse_unary(self):
        if token := self._match("MINUS"):
            operand = self._parse_unary()
            return UnaryOp("-", operand, self._loc(token))
        return self._parse_postfix()

    def _parse_postfix(self):
        expr = self._parse_primary()
        while True:
            if token := self._match("DOT"):
                name_token = self._expect("NAME", "Expected attribute name after '.'")
                expr = Attribute(expr, name_token.value, self._loc(token))
                continue
            if self._current().kind == "LPAREN":
                expr = self._parse_call(expr)
                continue
            break
        return expr

    def _parse_call(self, callee):
        lparen = self._expect("LPAREN", "Expected '('")
        args = []
        kwargs = []
        seen_keyword = False
        if self._current().kind != "RPAREN":
            while True:
                if self._current().kind == "NAME" and self._peek().kind == "EQ":
                    seen_keyword = True
                    key = self._advance().value
                    self._advance()  # EQ
                    value = self._parse_or()
                    if any(existing == key for existing, _ in kwargs):
                        self._error(f"Duplicate keyword argument '{key}'", self._current())
                    kwargs.append((key, value))
                else:
                    if seen_keyword:
                        self._error(
                            "Positional arguments cannot follow keyword arguments",
                            self._current(),
                        )
                    args.append(self._parse_or())

                if self._match("COMMA"):
                    if self._current().kind == "RPAREN":
                        break
                    continue
                break
        self._expect("RPAREN", "Expected ')' to close function call")
        return Call(callee, args, kwargs, self._loc(lparen))

    def _parse_primary(self):
        token = self._current()
        if token.kind == "NUMBER":
            self._advance()
            return Literal(int(token.value), self._loc(token))
        if token.kind == "STRING":
            self._advance()
            return Literal(token.value, self._loc(token))
        if token.kind == "TRUE":
            self._advance()
            return Literal(True, self._loc(token))
        if token.kind == "FALSE":
            self._advance()
            return Literal(False, self._loc(token))
        if token.kind == "NAME":
            self._advance()
            return Name(token.value, self._loc(token))
        if token.kind == "LPAREN":
            self._advance()
            expr = self._parse_or()
            self._expect("RPAREN", "Expected ')' after expression")
            return expr
        if token.kind == "LBRACK":
            return self._parse_list()
        self._error("Expected expression", token)

    def _parse_list(self):
        lbrack = self._expect("LBRACK", "Expected '['")
        items = []
        if self._current().kind != "RBRACK":
            while True:
                item = self._parse_or()
                if colon := self._match("COLON"):
                    end = self._parse_or()
                    items.append(RangeItem(item, end, self._loc(colon)))
                else:
                    items.append(item)
                if self._match("COMMA"):
                    if self._current().kind == "RBRACK":
                        break
                    continue
                break
        self._expect("RBRACK", "Expected ']' to close list")
        return ListLiteral(items, self._loc(lbrack))


class Parser:
    def __init__(self, source: str) -> None:
        self.source = source
        self.lines = source.splitlines()
        self.index = 0

    def parse(self) -> Program:
        statements = self._parse_block(expected_indent=0)
        return Program(statements)

    def _line_count(self) -> int:
        return len(self.lines)

    def _current_line(self) -> str:
        return self.lines[self.index]

    def _is_blank_or_comment(self, raw_line: str) -> bool:
        stripped = self._strip_comment(raw_line).strip()
        return stripped == ""

    def _strip_comment(self, raw_line: str) -> str:
        in_quote: str | None = None
        escaped = False
        for idx, char in enumerate(raw_line):
            if in_quote is not None:
                if escaped:
                    escaped = False
                    continue
                if char == "\\":
                    escaped = True
                    continue
                if char == in_quote:
                    in_quote = None
                continue
            if char in {"'", '"'}:
                in_quote = char
                continue
            if char == "#":
                return raw_line[:idx]
        return raw_line

    def _leading_indent(self, raw_line: str, line_no: int) -> int:
        if raw_line.startswith("\t"):
            self._raise("Tabs are not supported for indentation", line_no, 1)
        indent = 0
        while indent < len(raw_line):
            if raw_line[indent] == " ":
                indent += 1
                continue
            if raw_line[indent] == "\t":
                self._raise("Tabs are not supported for indentation", line_no, indent + 1)
            break
        return indent

    def _raise(self, message: str, line: int, column: int) -> None:
        source_line = self.lines[line - 1] if 1 <= line <= len(self.lines) else ""
        raise DSLSyntaxError(message, line, column, source_line)

    def _parse_block(self, expected_indent: int) -> list[Statement]:
        statements: list[Statement] = []
        while self.index < self._line_count():
            raw_line = self._current_line()
            line_no = self.index + 1
            if self._is_blank_or_comment(raw_line):
                self.index += 1
                continue

            indent = self._leading_indent(raw_line, line_no)
            if indent < expected_indent:
                break
            if indent > expected_indent:
                self._raise("Unexpected indentation", line_no, indent + 1)

            stripped = self._strip_comment(raw_line).rstrip()[indent:]
            statements.append(self._parse_statement(stripped, line_no, indent))
        return statements

    def _parse_statement(self, text: str, line_no: int, indent: int) -> Statement:
        if text.startswith("for "):
            return self._parse_for_statement(text, line_no, indent)
        if text.startswith("if "):
            return self._parse_if_statement(text, line_no, indent)
        if text.startswith("elif "):
            self._raise("'elif' without matching 'if'", line_no, indent + 1)
        if text == "else:":
            self._raise("'else' without matching 'if'", line_no, indent + 1)

        assign_index = self._find_assignment(text)
        if assign_index != -1:
            lhs = text[:assign_index].strip()
            rhs = text[assign_index + 1 :].strip()
            if not _IDENTIFIER_RE.match(lhs):
                self._raise(
                    "Invalid assignment target. Only simple variable names are allowed",
                    line_no,
                    indent + 1,
                )
            if rhs == "":
                self._raise(
                    "Missing expression on right side of assignment",
                    line_no,
                    indent + assign_index + 2,
                )
            expr_col = indent + text.index(rhs) + 1
            rhs_full, consumed = self._collect_continued_expression(rhs, line_no)
            expr = self._parse_expression(rhs_full, line_no, expr_col)
            self.index += consumed
            return Assign(lhs, expr, SourceLocation(line_no, indent + 1))

        expr_text, consumed = self._collect_continued_expression(text, line_no)
        expr = self._parse_expression(expr_text, line_no, indent + 1)
        self.index += consumed
        return ExprStatement(expr, SourceLocation(line_no, indent + 1))

    def _collect_continued_expression(self, text: str, line_no: int) -> tuple[str, int]:
        expression = text
        balance = self._delimiter_balance(text)
        consumed = 1

        while balance > 0:
            next_index = self.index + consumed
            if next_index >= self._line_count():
                self._raise("Unterminated expression. Missing closing bracket/parenthesis", line_no, 1)

            next_line = self._strip_comment(self.lines[next_index]).strip()
            expression = f"{expression}\n{next_line}"
            balance += self._delimiter_balance(next_line)
            consumed += 1

        return expression, consumed

    def _delimiter_balance(self, text: str) -> int:
        balance = 0
        in_quote: str | None = None
        escaped = False

        for char in text:
            if in_quote is not None:
                if escaped:
                    escaped = False
                    continue
                if char == "\\":
                    escaped = True
                    continue
                if char == in_quote:
                    in_quote = None
                continue

            if char in {"'", '"'}:
                in_quote = char
                continue
            if char in {"(", "["}:
                balance += 1
                continue
            if char in {")", "]"}:
                balance -= 1
        return balance

    def _parse_for_statement(self, text: str, line_no: int, indent: int) -> ForStatement:
        match = _FOR_RE.match(text)
        if not match:
            self._raise("Invalid for-loop syntax. Use: for item in iterable:", line_no, indent + 1)
        var_name = match.group(1)
        iterable_text = match.group(2).strip()
        iterable_col = indent + text.index(iterable_text) + 1
        iterable = self._parse_expression(iterable_text, line_no, iterable_col)
        self.index += 1
        body = self._parse_child_block(parent_indent=indent, parent_line=line_no, parent_col=indent + 1)
        return ForStatement(var_name, iterable, body, SourceLocation(line_no, indent + 1))

    def _parse_if_statement(self, text: str, line_no: int, indent: int) -> IfStatement:
        match = _IF_RE.match(text)
        if not match:
            self._raise("Invalid if syntax. Use: if condition:", line_no, indent + 1)
        condition_text = match.group(1).strip()
        condition_col = indent + text.index(condition_text) + 1
        condition = self._parse_expression(condition_text, line_no, condition_col)
        self.index += 1
        body = self._parse_child_block(parent_indent=indent, parent_line=line_no, parent_col=indent + 1)
        branches = [(condition, body)]
        else_body = None

        while self.index < self._line_count():
            scan = self.index
            while scan < self._line_count() and self._is_blank_or_comment(self.lines[scan]):
                scan += 1
            if scan >= self._line_count():
                self.index = scan
                break

            raw_line = self.lines[scan]
            scan_line_no = scan + 1
            scan_indent = self._leading_indent(raw_line, scan_line_no)
            if scan_indent != indent:
                self.index = scan
                break

            stripped = self._strip_comment(raw_line).rstrip()[scan_indent:]
            if stripped.startswith("elif "):
                if else_body is not None:
                    self._raise("'elif' cannot appear after 'else'", scan_line_no, scan_indent + 1)
                elif_match = _ELIF_RE.match(stripped)
                if not elif_match:
                    self._raise("Invalid elif syntax. Use: elif condition:", scan_line_no, scan_indent + 1)
                cond_text = elif_match.group(1).strip()
                cond_col = scan_indent + stripped.index(cond_text) + 1
                cond = self._parse_expression(cond_text, scan_line_no, cond_col)
                self.index = scan + 1
                elif_body = self._parse_child_block(
                    parent_indent=scan_indent,
                    parent_line=scan_line_no,
                    parent_col=scan_indent + 1,
                )
                branches.append((cond, elif_body))
                continue

            if stripped == "else:":
                if else_body is not None:
                    self._raise("Only one else block is allowed", scan_line_no, scan_indent + 1)
                self.index = scan + 1
                else_body = self._parse_child_block(
                    parent_indent=scan_indent,
                    parent_line=scan_line_no,
                    parent_col=scan_indent + 1,
                )
                continue

            self.index = scan
            break

        return IfStatement(branches, else_body, SourceLocation(line_no, indent + 1))

    def _parse_child_block(self, parent_indent: int, parent_line: int, parent_col: int) -> list[Statement]:
        scan = self.index
        while scan < self._line_count() and self._is_blank_or_comment(self.lines[scan]):
            scan += 1
        if scan >= self._line_count():
            self._raise("Expected an indented block", parent_line, parent_col)
        child_line = self.lines[scan]
        child_line_no = scan + 1
        child_indent = self._leading_indent(child_line, child_line_no)
        if child_indent <= parent_indent:
            self._raise("Expected an indented block", child_line_no, child_indent + 1)
        self.index = scan
        return self._parse_block(expected_indent=child_indent)

    def _find_assignment(self, text: str) -> int:
        depth = 0
        in_quote: str | None = None
        escaped = False
        for idx, char in enumerate(text):
            if in_quote is not None:
                if escaped:
                    escaped = False
                    continue
                if char == "\\":
                    escaped = True
                    continue
                if char == in_quote:
                    in_quote = None
                continue

            if char in {"'", '"'}:
                in_quote = char
                continue
            if char in {"(", "["}:
                depth += 1
                continue
            if char in {")", "]"}:
                depth = max(depth - 1, 0)
                continue
            if char != "=" or depth != 0:
                continue

            prev_char = text[idx - 1] if idx > 0 else ""
            next_char = text[idx + 1] if idx + 1 < len(text) else ""
            if prev_char in {"=", "!", "<", ">"} or next_char == "=":
                continue
            return idx
        return -1

    def _parse_expression(self, text: str, line_no: int, column: int):
        lexer = ExpressionLexer(text, base_column=column, line=line_no, source_line=self.lines[line_no - 1])
        tokens = lexer.tokenize()
        parser = ExpressionParser(
            tokens=tokens,
            line=line_no,
            source_line=self.lines[line_no - 1],
            base_column=column,
        )
        return parser.parse()
