# FilesDSL Documentation

## Overview
FilesDSL is a constrained language for file exploration by LLM agents. It supports:
1. Safe directory traversal.
2. Full/chunked document reading.
3. Regex-based search on file names and file contents.
4. Basic control flow for analysis scripts.

The DSL is intentionally small to reduce agent risk and improve predictability.

## Run Scripts
```bash
uv run python -m filesdsl path/to/script.fdsl
```

Optional sandbox root:
```bash
uv run python -m filesdsl path/to/script.fdsl --sandbox-root .
```

## Core Syntax

### Variables
Supported values:
1. `int`
2. `bool` (`true`, `false`)
3. `string`
4. `list`

Example:
```fdsl
folder = Directory("data")
pattern = "transformer"
pages = [1, 3:5, 10]
```

### Control Flow
Supported:
1. `for ... in ...:`
2. `if ...:`
3. `elif ...:`
4. `else:`

Example:
```fdsl
for file in folder:
    if file.contains(pattern, ignore_case=true):
        print(file)
```

### Expressions
Supported operators:
1. Arithmetic: `+ - * / %`
2. Comparisons: `== != < <= > >=`
3. Boolean: `and or not`

### Built-ins
1. `print(...)`
2. `len(...)`
3. `Directory(path, recursive=true)`

## Directory API

### `Directory(path, recursive=true)`
Creates a directory object, constrained by sandbox rules.

### Iteration
```fdsl
docs = Directory("data")
for file in docs:
    print(file)
```

### `dir.files(recursive=None)`
Returns a list of file objects.

Defaults:
1. `recursive=None` means "use the directory object's own recursive setting".
2. Since `Directory(..., recursive=true)` by default, `files()` is recursive by default.

### `dir.search(pattern, scope="name", in_content=false, recursive=None, ignore_case=false)`
Returns a list of matching file objects.

Notes:
1. `pattern` is a regex.
2. `in_content=true` is a shorthand that forces content search.
3. `scope="name"` checks filename/path only.
4. `scope="content"` checks file content only.
5. `scope="both"` checks either.
6. `recursive=None` means "use the directory object's own recursive setting".

## File API

### `file.read(pages=None)`
1. `read()` returns full content as one string.
2. `read(pages=[...])` returns a list of selected pages/chunks.
3. Default is `pages=None`.

Page selection supports inclusive ranges inside list literals:
```fdsl
content = file.read(pages=[1, 5:8, 12])
```
This expands to pages `1, 5, 6, 7, 8, 12`.

### `file.search(pattern, ignore_case=false) -> list[int]`
Returns matching page/chunk numbers.

### `file.contains(pattern, ignore_case=false) -> bool`
Returns whether any page/chunk matches.

### `file.head() -> string`
Returns first page/chunk.

### `file.tail() -> string`
Returns last page/chunk.

### `file.snippets(pattern, max_results=5, context_chars=80, ignore_case=false) -> list[string]`
Returns contextual snippets for each regex match.

### `file.table(max_items=50) -> string`
Returns an indented table-of-contents tree with page numbers when detected.

If no TOC is found:
```text
No table of contents detected for <file-path>
```

## Default Values Summary
1. `Directory(path, recursive=true)`
2. `dir.files(recursive=None)` where `None` => directory default
3. `dir.search(pattern, scope="name", in_content=false, recursive=None, ignore_case=false)`
4. `file.read(pages=None)`
5. `file.search(pattern, ignore_case=false)`
6. `file.contains(pattern, ignore_case=false)`
7. `file.snippets(pattern, max_results=5, context_chars=80, ignore_case=false)`
8. `file.table(max_items=50)`

## PDF Handling
PDF parsing uses `pymupdf` (PyMuPDF):
1. Page text extraction for `read/search/contains`.
2. PDF bookmarks/outlines for high-quality TOC output in `file.table()`.

## Error Model

### Syntax errors
Include:
1. Message.
2. Line and column.
3. Source line + pointer.

### Runtime errors
Include:
1. Message.
2. Call location when available.
3. Clear failure reason (invalid regex, page out of range, sandbox denial, etc.).

## Security Model
1. No imports.
2. No arbitrary Python execution.
3. Only whitelisted built-ins and object methods.
4. Directory access is sandboxed to the configured root.

## End-to-End Example
```fdsl
docs = Directory("data")
matches = docs.search(".*\\.pdf$", scope="name")

for file in matches:
    if file.contains("language model", ignore_case=true):
        print("FILE:", file)
        print("TOC:")
        print(file.table())
        hit_pages = file.search("language model", ignore_case=true)
        print("MATCH PAGES:", hit_pages)
        print("FIRST PAGE:")
        print(file.read(pages=[1]))
```
