# FilesDSL Documentation

> For a detailed breakdown of the current FAISS-based indexing/storage flow, see `docs/FAISS_INDEXING.md`.

## Overview
FilesDSL is a constrained language for file exploration by LLM agents. It supports:
1. Safe directory traversal.
2. Full/chunked document reading.
3. Regex-based search on file names and file contents.
4. Basic control flow for analysis scripts.
5. PDF, DOCX, and PPTX content extraction.

The DSL is intentionally small to reduce agent risk and improve predictability.

## Run Scripts
```bash
uv run python -m filesdsl path/to/script.fdsl
```

Optional sandbox root:
```bash
uv run python -m filesdsl path/to/script.fdsl --sandbox-root .
```

Prepare semantic index (recursive, page-level embeddings):
```bash
uv run fdsl prepare path/to/folder
```

## Python Integration
Use `execute_fdsl(...)` when you run FDSL from Python and want console history.

```python
from filesdsl import execute_fdsl

code = """
print("hello")
print([1, 2, 3])
"""

history = execute_fdsl(code, cwd=".", sandbox_root=".")
# history == "hello\n[1, 2, 3]\n"
```

Default arguments:
1. `cwd=None` (uses current working directory)
2. `sandbox_root=None` (defaults to `cwd`)

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
2. Comparisons: `== != < <= > >= in`
3. Boolean: `and or not`

Membership notes:
1. `value in [1, 2, 3]` follows Python list membership semantics.
2. `"part" in "text"` follows Python substring semantics.
3. `"part" in File(...)` checks the file name.
4. `"part" in Directory(...)` checks the directory name.

### Built-ins
1. `print(...)`
2. `len(...)`
3. `Directory(path, recursive=true)`
4. `File(path)`

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

### `dir.semantic_search(query, top_k=5, recursive=None) -> list[string]`
Returns top semantic chunk matches for a natural-language query across files in the directory.

Notes:
1. Requires a prepared semantic index: `fdsl prepare <folder>`.
2. `query` must be a non-empty string.
3. `top_k` must be a positive integer.
4. `recursive=None` means "use the directory object's own recursive setting".
5. Results are returned as formatted chunks ordered by descending similarity:
   `[relative/path.ext] => [p.<n>] <chunk-text>`

### `dir.tree(max_depth=5, max_entries=500) -> string`
Returns an indented textual tree of directories/files rooted at this directory.

Notes:
1. Directories are suffixed with `/`.
2. `max_depth=0` returns only the root line.
3. If entry count exceeds `max_entries`, output ends with:
   `... truncated after <max_entries> entries`

## File API

### `File(path)`
Creates a file object directly without iterating or searching a directory.

Example:
```fdsl
report = File("data/office_samples/project_status_report.docx")
print(report.head())
```

### `file.read(pages=None)`
1. `read()` returns full content as one string.
2. `read(pages=<int>)` returns a single page/chunk as a string.
3. `read(pages=[...])` returns a list of selected pages/chunks.
4. Default is `pages=None`.
5. On PPTX, each slide maps to one chunk/page.
6. On DOCX, chunks are section-like groups based on headings/content.
7. Every returned page/chunk is prefixed as:
   `[{filename}] => [p.{i}] {content}`

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

### `file.semantic_search(query, top_k=5) -> list[string]`
Runs semantic retrieval over a prepared index and returns the top-k
most similar chunks for this file.

Notes:
1. `query` must be a non-empty string.
2. `top_k` must be a positive integer.
3. Returns formatted chunks:
   `[filename.ext] => [p.<n>] <chunk-text>`
4. Requires a previously prepared index with:
   `fdsl prepare <folder>`

### `file.table(max_items=50) -> string`
Returns a formatted TOC block when available:

```text
=== Table of contents for file <file-path> ===
<indented toc tree>
```

The indented TOC tree includes location metadata when available.

Examples of location metadata:
1. PDF: page numbers, e.g. `(p.12)`
2. PPTX: slide numbers, e.g. `(p.3)`
3. DOCX: typically headings only (usually no page numbers)

If no TOC is found:
```text
No table of contents detected for <file-path>
```

## Default Values Summary
1. `Directory(path, recursive=true)`
2. `File(path)` (no optional defaults; `path` is required)
3. `dir.files(recursive=None)` where `None` => directory default
4. `dir.search(pattern, scope="name", in_content=false, recursive=None, ignore_case=false)`
5. `dir.semantic_search(query, top_k=5, recursive=None)`
6. `dir.tree(max_depth=5, max_entries=500)`
7. `file.read(pages=None)`
8. `file.search(pattern, ignore_case=false)`
9. `file.contains(pattern, ignore_case=false)`
10. `file.snippets(pattern, max_results=5, context_chars=80, ignore_case=false)`
11. `file.semantic_search(query, top_k=5)`
12. `file.table(max_items=50)`

## Format Handling
PDF parsing uses `pymupdf` (PyMuPDF):
1. Page text extraction for `read/search/contains`.
2. PDF bookmarks/outlines for high-quality TOC output in `file.table()`.

Word parsing uses `python-docx`:
1. Paragraph/heading extraction for `read/search/contains`.
2. Heading styles for TOC extraction in `file.table()`.

PowerPoint parsing uses `python-pptx`:
1. Slide text extraction for `read/search/contains`.
2. Slide titles for TOC extraction in `file.table()`.
3. Slides are treated as page/chunk units.

Semantic indexing uses:
1. `chromadb` for persistent vector storage.
2. Chroma's built-in `ONNXMiniLM_L6_V2` embedding model (MiniLM-v2).
3. Page-level embeddings with file name included in embedding input.

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

docx = File("data/office_samples/project_status_report.docx")
print("DOCX TOC:")
print(docx.table())

pptx = File("data/office_samples/project_kickoff_deck.pptx")
print("PPTX SLIDES:")
print(pptx.table())
```
