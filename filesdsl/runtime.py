from __future__ import annotations

import re
from pathlib import Path

from .errors import DSLRuntimeError


def _compile_regex(pattern: str, ignore_case: bool = False) -> re.Pattern[str]:
    if not isinstance(pattern, str):
        raise DSLRuntimeError("Regex pattern must be a string")
    flags = re.IGNORECASE if ignore_case else 0
    try:
        return re.compile(pattern, flags)
    except re.error as exc:
        raise DSLRuntimeError(f"Invalid regex pattern: {exc}") from exc


class DSLFile:
    def __init__(self, path: Path, text_chunk_lines: int = 80) -> None:
        self.path = path
        self._text_chunk_lines = text_chunk_lines
        self._chunks_cache: list[str] | None = None

    def __repr__(self) -> str:
        return f"File('{self.path.as_posix()}')"

    def __str__(self) -> str:
        return self.path.as_posix()

    def read(self, pages=None):
        chunks = self._chunks()
        if pages is None:
            return "\n\n".join(chunks)
        selected = self._normalize_pages(pages, total_pages=len(chunks))
        return [chunks[idx - 1] for idx in selected]

    def search(self, pattern: str, ignore_case: bool = False) -> list[int]:
        regex = _compile_regex(pattern, ignore_case=ignore_case)
        matches = []
        for page_index, chunk in enumerate(self._chunks(), start=1):
            if regex.search(chunk):
                matches.append(page_index)
        return matches

    def contains(self, pattern: str, ignore_case: bool = False) -> bool:
        return bool(self.search(pattern, ignore_case=ignore_case))

    def head(self):
        chunks = self._chunks()
        if not chunks:
            return ""
        return chunks[0]

    def tail(self):
        chunks = self._chunks()
        if not chunks:
            return ""
        return chunks[-1]

    def table(self, max_items: int = 50) -> str:
        if not isinstance(max_items, int) or max_items < 1:
            raise DSLRuntimeError("max_items must be a positive integer")

        entries: list[tuple[int, str, int | None]] = []
        if self.path.suffix.lower() == ".pdf":
            entries = self._read_pdf_outline(max_items=max_items)
        if not entries:
            entries = self._extract_toc_entries_from_text(max_items=max_items)
        if not entries:
            return f"No table of contents detected for {self.path.as_posix()}"
        return self._format_toc_tree(entries)

    def snippets(
        self,
        pattern: str,
        max_results: int = 5,
        context_chars: int = 80,
        ignore_case: bool = False,
    ) -> list[str]:
        if not isinstance(max_results, int) or max_results < 1:
            raise DSLRuntimeError("max_results must be a positive integer")
        if not isinstance(context_chars, int) or context_chars < 0:
            raise DSLRuntimeError("context_chars must be a non-negative integer")
        regex = _compile_regex(pattern, ignore_case=ignore_case)

        snippets: list[str] = []
        for page_index, chunk in enumerate(self._chunks(), start=1):
            for match in regex.finditer(chunk):
                start = max(match.start() - context_chars, 0)
                end = min(match.end() + context_chars, len(chunk))
                excerpt = chunk[start:end].replace("\n", " ").strip()
                snippets.append(f"[page {page_index}] {excerpt}")
                if len(snippets) >= max_results:
                    return snippets
        return snippets

    def _normalize_pages(self, pages, total_pages: int) -> list[int]:
        if isinstance(pages, int):
            pages_values = [pages]
        elif isinstance(pages, list):
            pages_values = pages
        else:
            raise DSLRuntimeError("pages must be an integer or a list of integers")

        normalized: list[int] = []
        for value in pages_values:
            if not isinstance(value, int):
                raise DSLRuntimeError("pages list must contain only integers")
            if value < 1 or value > total_pages:
                raise DSLRuntimeError(
                    f"Page {value} is out of range for {self.path.name} (1..{total_pages})"
                )
            if value not in normalized:
                normalized.append(value)
        return normalized

    def _chunks(self) -> list[str]:
        if self._chunks_cache is not None:
            return self._chunks_cache

        suffix = self.path.suffix.lower()
        if suffix == ".pdf":
            chunks = self._read_pdf_pages()
        else:
            chunks = self._read_text_chunks()
        self._chunks_cache = chunks or [""]
        return self._chunks_cache

    def _read_pdf_pages(self) -> list[str]:
        try:
            import pymupdf
        except ImportError as exc:
            raise DSLRuntimeError(
                "PyMuPDF is required to read PDF files. Install dependency 'pymupdf'."
            ) from exc

        try:
            with pymupdf.open(str(self.path)) as doc:
                pages = [page.get_text("text").strip() for page in doc]
        except Exception as exc:
            raise DSLRuntimeError(f"Failed to read PDF '{self.path.name}': {exc}") from exc

        return pages or [""]

    def _read_pdf_outline(self, max_items: int) -> list[tuple[int, str, int | None]]:
        try:
            import pymupdf
        except ImportError as exc:
            raise DSLRuntimeError(
                "PyMuPDF is required to read PDF files. Install dependency 'pymupdf'."
            ) from exc

        try:
            with pymupdf.open(str(self.path)) as doc:
                raw_toc = doc.get_toc(simple=True)
        except Exception as exc:
            raise DSLRuntimeError(f"Failed to read PDF outline '{self.path.name}': {exc}") from exc

        entries: list[tuple[int, str, int | None]] = []
        for item in raw_toc:
            if not isinstance(item, (list, tuple)) or len(item) < 3:
                continue
            raw_level, raw_title, raw_page = item[0], item[1], item[2]
            if not isinstance(raw_level, int):
                continue
            level = max(1, raw_level)
            title = str(raw_title).strip()
            if not title:
                continue

            page: int | None = None
            if isinstance(raw_page, int):
                page = raw_page if raw_page >= 1 else None
            elif isinstance(raw_page, float):
                page_candidate = int(raw_page)
                page = page_candidate if page_candidate >= 1 else None

            entries.append((level, title, page))
            if len(entries) >= max_items:
                break
        return entries

    def _extract_toc_entries_from_text(self, max_items: int) -> list[tuple[int, str, int | None]]:
        numbered_dotted = re.compile(r"^(\d+(?:\.\d+)*)\s+(.+?)\.{2,}\s*(\d+)$")
        numbered_plain = re.compile(r"^(\d+(?:\.\d+)*)\s+(.+?)\s+(\d+)$")
        titled_dotted = re.compile(r"^(.+?)\.{2,}\s*(\d+)$")
        entries: list[tuple[int, str, int | None]] = []
        seen: set[tuple[int, str, int | None]] = set()

        for chunk in self._chunks()[:8]:
            for raw_line in chunk.splitlines():
                line = raw_line.strip()
                if len(line) < 8:
                    continue

                level = 1
                title = ""
                page: int | None = None

                match = numbered_dotted.match(line) or numbered_plain.match(line)
                if match:
                    section = match.group(1).strip()
                    body = match.group(2).strip()
                    title = f"{section} {body}".strip()
                    page = int(match.group(3))
                    level = section.count(".") + 1
                else:
                    title_match = titled_dotted.match(line)
                    if title_match:
                        title = title_match.group(1).strip()
                        page = int(title_match.group(2))

                if not title:
                    continue
                key = (level, title, page)
                if key in seen:
                    continue
                seen.add(key)
                entries.append(key)
                if len(entries) >= max_items:
                    return entries
        return entries

    def _format_toc_tree(self, entries: list[tuple[int, str, int | None]]) -> str:
        lines: list[str] = []
        for level, title, page in entries:
            indent = "  " * max(level - 1, 0)
            page_text = f" (p.{page})" if page is not None else ""
            lines.append(f"{indent}{title}{page_text}")
        return "\n".join(lines)

    def _read_text_chunks(self) -> list[str]:
        try:
            text = self.path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            text = self.path.read_text(encoding="utf-8", errors="replace")

        if text == "":
            return [""]

        lines = text.splitlines()
        if not lines:
            return [text]

        chunks: list[str] = []
        for start in range(0, len(lines), self._text_chunk_lines):
            block = "\n".join(lines[start : start + self._text_chunk_lines]).strip()
            chunks.append(block)
        return chunks or [text]


class DSLDirectory:
    def __init__(self, path: Path, recursive: bool = True) -> None:
        if not path.exists():
            raise DSLRuntimeError(f"Directory does not exist: {path.as_posix()}")
        if not path.is_dir():
            raise DSLRuntimeError(f"Path is not a directory: {path.as_posix()}")
        self.path = path
        self.recursive = recursive

    def __repr__(self) -> str:
        return f"Directory('{self.path.as_posix()}')"

    def __str__(self) -> str:
        return self.path.as_posix()

    def __iter__(self):
        files = self._iter_file_paths(self.recursive)
        for file_path in files:
            yield DSLFile(file_path)

    def files(self, recursive: bool | None = None) -> list[DSLFile]:
        if recursive is None:
            recursive = self.recursive
        return [DSLFile(path) for path in self._iter_file_paths(recursive)]

    def search(
        self,
        pattern: str,
        scope: str = "name",
        in_content: bool = False,
        recursive: bool | None = None,
        ignore_case: bool = False,
    ) -> list[DSLFile]:
        if recursive is None:
            recursive = self.recursive
        if in_content:
            scope = "content"
        if scope not in {"name", "content", "both"}:
            raise DSLRuntimeError("scope must be one of: 'name', 'content', 'both'")

        regex = _compile_regex(pattern, ignore_case=ignore_case)
        files = [DSLFile(path) for path in self._iter_file_paths(recursive)]
        matches: list[DSLFile] = []
        for file in files:
            relative = file.path.relative_to(self.path).as_posix()
            name_match = bool(regex.search(file.path.name) or regex.search(relative))
            content_match = False
            if scope in {"content", "both"}:
                content_match = file.contains(pattern, ignore_case=ignore_case)

            if scope == "name" and name_match:
                matches.append(file)
            elif scope == "content" and content_match:
                matches.append(file)
            elif scope == "both" and (name_match or content_match):
                matches.append(file)
        return matches

    def _iter_file_paths(self, recursive: bool) -> list[Path]:
        if recursive:
            paths = [path for path in self.path.rglob("*") if path.is_file()]
        else:
            paths = [path for path in self.path.glob("*") if path.is_file()]
        paths.sort(key=lambda p: p.as_posix())
        return paths
