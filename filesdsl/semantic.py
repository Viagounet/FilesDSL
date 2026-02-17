from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from .errors import DSLRuntimeError


SEMANTIC_DB_DIRNAME = ".fdsl_chroma"
SEMANTIC_COLLECTION_NAME = "pages"
_EMBEDDING_FUNCTION = None


@dataclass(frozen=True)
class PrepareStats:
    folder: Path
    db_path: Path
    indexed_files: int
    indexed_pages: int


def prepare_semantic_database(folder: Path) -> PrepareStats:
    target_folder = folder.resolve()
    if not target_folder.exists():
        raise DSLRuntimeError(f"Folder does not exist: {target_folder.as_posix()}")
    if not target_folder.is_dir():
        raise DSLRuntimeError(f"Path is not a directory: {target_folder.as_posix()}")

    db_path = target_folder / SEMANTIC_DB_DIRNAME
    db_path.mkdir(parents=True, exist_ok=True)
    collection = _create_fresh_collection(db_path)

    indexed_files = 0
    indexed_pages = 0

    ids: list[str] = []
    documents: list[str] = []
    embedding_inputs: list[str] = []
    metadatas: list[dict[str, str | int]] = []

    def flush_batch() -> None:
        if not ids:
            return
        embeddings = _encode_texts(embedding_inputs)
        try:
            collection.upsert(
                ids=ids,
                embeddings=embeddings,
                documents=documents,
                metadatas=metadatas,
            )
        except Exception as exc:
            raise DSLRuntimeError(f"Failed to write semantic index: {exc}") from exc
        ids.clear()
        documents.clear()
        embedding_inputs.clear()
        metadatas.clear()

    for file_path in _iter_document_paths(target_folder):
        relative_path = file_path.relative_to(target_folder).as_posix()
        pages = _extract_pages(file_path, display_root=target_folder)
        indexed_files += 1

        for page_number, page_text in enumerate(pages, start=1):
            cleaned = page_text.strip()
            embedding_text = f"File: {relative_path}\n{cleaned}" if cleaned else f"File: {relative_path}"
            record_id = f"{relative_path}::page::{page_number}"
            ids.append(record_id)
            documents.append(cleaned)
            embedding_inputs.append(embedding_text)
            metadatas.append(
                {
                    "relative_path": relative_path,
                    "file_name": file_path.name,
                    "page": page_number,
                }
            )
            indexed_pages += 1
            if len(ids) >= 64:
                flush_batch()

    flush_batch()
    return PrepareStats(
        folder=target_folder,
        db_path=db_path,
        indexed_files=indexed_files,
        indexed_pages=indexed_pages,
    )


def semantic_search_file_pages(
    file_path: Path,
    query: str,
    top_k: int,
    *,
    display_root: Path | None = None,
) -> list[int]:
    if not isinstance(query, str) or query.strip() == "":
        raise DSLRuntimeError("query must be a non-empty string")
    if not isinstance(top_k, int) or top_k < 1:
        raise DSLRuntimeError("top_k must be a positive integer")

    resolved_file_path = file_path.resolve()
    indexed_root = _find_indexed_root(resolved_file_path, display_root=display_root)
    relative_path = resolved_file_path.relative_to(indexed_root).as_posix()
    collection = _load_collection(indexed_root / SEMANTIC_DB_DIRNAME)

    query_embedding = _encode_texts([query.strip()])[0]
    try:
        result = collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where={"relative_path": relative_path},
            include=["metadatas"],
        )
    except Exception as exc:
        raise DSLRuntimeError(f"Semantic query failed: {exc}") from exc

    metadatas = []
    if isinstance(result, dict):
        raw = result.get("metadatas")
        if isinstance(raw, list) and raw:
            first = raw[0]
            if isinstance(first, list):
                metadatas = first

    pages: list[int] = []
    for metadata in metadatas:
        if not isinstance(metadata, dict):
            continue
        page = metadata.get("page")
        if isinstance(page, int):
            pages.append(page)
        elif isinstance(page, float):
            pages.append(int(page))
    return pages


def _iter_document_paths(folder: Path):
    db_path = folder / SEMANTIC_DB_DIRNAME
    for path in sorted(folder.rglob("*"), key=lambda p: p.as_posix()):
        if not path.is_file():
            continue
        if db_path in path.parents:
            continue
        yield path


def _extract_pages(path: Path, display_root: Path) -> list[str]:
    from .runtime import DSLFile

    file_obj = DSLFile(path, display_root=display_root)
    try:
        return file_obj._chunks()
    except DSLRuntimeError:
        raise
    except Exception as exc:
        raise DSLRuntimeError(f"Failed to extract pages from '{path.name}': {exc}") from exc


def _render_relative_path(path: Path, cwd: Path) -> str:
    try:
        return Path(os.path.relpath(path.resolve(), cwd.resolve())).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _find_indexed_root(file_path: Path, display_root: Path | None = None) -> Path:
    display_base = (display_root or Path.cwd()).resolve()
    for candidate in [file_path.parent, *file_path.parents]:
        if (candidate / SEMANTIC_DB_DIRNAME).is_dir():
            return candidate
    rendered = _render_relative_path(file_path, display_base)
    raise DSLRuntimeError(
        f"No semantic index found for {rendered}. "
        "Run 'uv run fdsl prepare <folder>' first."
    )


def _require_chromadb():
    try:
        import chromadb
    except ImportError as exc:
        raise DSLRuntimeError(
            "chromadb is required for semantic indexing. Install dependency 'chromadb'."
        ) from exc
    return chromadb


def _get_embedding_function():
    global _EMBEDDING_FUNCTION
    if _EMBEDDING_FUNCTION is None:
        try:
            from chromadb.utils import embedding_functions
        except Exception as exc:
            raise DSLRuntimeError(f"Failed to load Chroma embedding helpers: {exc}") from exc

        try:
            _EMBEDDING_FUNCTION = embedding_functions.ONNXMiniLM_L6_V2()
        except Exception as exc:
            raise DSLRuntimeError(
                "Failed to initialize MiniLM-v2 embedding function via chromadb: "
                f"{exc}"
            ) from exc
    return _EMBEDDING_FUNCTION


def _encode_texts(texts: list[str]) -> list[list[float]]:
    embedding_function = _get_embedding_function()
    try:
        embeddings = embedding_function(texts)
    except Exception as exc:
        raise DSLRuntimeError(f"Embedding generation failed: {exc}") from exc

    vectors: list[list[float]] = []
    for vector in embeddings:
        vectors.append([float(value) for value in vector])
    return vectors


def _create_fresh_collection(db_path: Path):
    chromadb = _require_chromadb()
    client = chromadb.PersistentClient(path=str(db_path))
    try:
        client.delete_collection(name=SEMANTIC_COLLECTION_NAME)
    except Exception:
        pass
    return client.get_or_create_collection(name=SEMANTIC_COLLECTION_NAME)


def _load_collection(db_path: Path):
    chromadb = _require_chromadb()
    client = chromadb.PersistentClient(path=str(db_path))
    try:
        return client.get_collection(name=SEMANTIC_COLLECTION_NAME)
    except Exception as exc:
        raise DSLRuntimeError(
            "No prepared semantic index collection found. "
            "Run 'uv run fdsl prepare <folder>' first."
        ) from exc
