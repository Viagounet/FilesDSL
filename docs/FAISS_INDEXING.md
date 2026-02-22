# FAISS Indexing and Runtime Data Flow

This document explains exactly what happens when you run:

```bash
uv run fdsl prepare <folder>
```

and how `Directory(...)` / `File(...)` operations behave afterwards.

## 1) What `fdsl prepare` builds

`prepare_semantic_database(folder)` creates a local index directory at:

- `<folder>/.fdsl_faiss`

Inside it, FilesDSL stores:

- `records.json`: one record per extracted page/chunk
- `vectors.json`: one embedding vector per record
- `meta.json`: embedding metadata/version used to validate vector compatibility
- `pages.faiss`: FAISS marker/index file used to represent the FAISS-backed store

Each `records.json` record stores:

- `relative_path`: path relative to the prepared root
- `file_name`: basename
- `page`: page/chunk number (1-based)
- `text`: extracted content for that page/chunk

So page text is persisted in the database layer and can be read later without re-opening the source file.

---

## 2) How text extraction works during indexing

During `prepare`, FilesDSL walks files under the target folder (excluding `.fdsl_faiss`) and extracts content by extension.

### PDF (`.pdf`)

1. Try PyMuPDF (`pymupdf`) page text extraction.
2. If a page has no text (typical scanned page), use OCR fallback:
   - render page to image
   - run Tesseract (`pytesseract` + Pillow)

### DOCX (`.docx`)

1. Try `python-docx`.
2. If unavailable or failing, fallback by reading `word/document.xml` from the zip and extracting text nodes.

### PPTX (`.pptx`)

1. Try `python-pptx`.
2. If unavailable or failing, fallback by reading slide XML files from the zip and extracting text nodes.

### Other files

- Read as UTF-8 text chunks.

---

## 3) Runtime behavior after indexing

## `File.read()`, `File.search()`, `File.contains()`, `File.head()`, `File.tail()`, `File.snippets()`

All these methods depend on `DSLFile._chunks()`.

`_chunks()` logic is:

1. Try `get_file_pages_from_database(...)` from `.fdsl_faiss/records.json`.
2. If found, use DB pages.
3. If not found, fallback to physical file readers (PyMuPDF/docx/pptx/text).

This means: **when indexed data exists, read/search operations run directly on DB-stored page content.**

## `Directory(...)` iteration and `search(...)`

`DSLDirectory._iter_file_paths(...)` first calls `get_directory_file_paths_from_database(...)`.

- If DB entries exist, it returns file paths reconstructed from DB records.
- If no index exists, it falls back to filesystem traversal (`rglob`/`glob`).

So directory listing/search can continue working from the prepared database view.

## `File("...")` constructor behavior

Interpreter logic allows constructing `File(path)` if either:

- the file exists physically, or
- the file is present in the prepared DB records

This lets scripts keep operating on indexed files even if the original files are moved/removed.

---

## 4) Semantic search flow (`file.semantic_search(...)` / `dir.semantic_search(...)`)

`semantic_search_file_chunks(...)`:

1. Finds the nearest indexed root containing `.fdsl_faiss`
2. Loads `records.json` + `vectors.json`
3. Auto-rebuilds vectors when legacy/incompatible metadata is detected
4. Filters records to the requested file path
5. Scores by dot-product similarity
6. Returns top-k chunks with page numbers

Embeddings now use a deterministic token hashing strategy (`blake2b` buckets), so
prepare-time and query-time vectors stay compatible across different Python processes.
Legacy indexes are upgraded automatically on first semantic query.

`semantic_search_directory_chunks(...)`:

1. Finds the nearest indexed root containing `.fdsl_faiss`
2. Loads `records.json` + `vectors.json`
3. Auto-rebuilds vectors when legacy/incompatible metadata is detected
4. Filters records to files under the target directory (`recursive` aware)
5. Scores each chunk by dot-product similarity
6. Returns top-k chunks with file path + page metadata

---

## 5) Practical execution summary

After `fdsl prepare data`, the typical execution model is:

- **Prepare phase**: extract and store page text + vectors in `.fdsl_faiss`
- **Runtime phase**: prefer DB-backed content/path listing; fallback to direct file parsing only when DB data is missing

This is what enables directory/file operations to stay consistent with the prepared index and use the indexed representation as the primary source.
