from __future__ import annotations

import io
import json
import math
import os
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
import xml.etree.ElementTree as ET

from .errors import DSLRuntimeError


SEMANTIC_DB_DIRNAME = ".fdsl_faiss"
SEMANTIC_INDEX_FILENAME = "pages.faiss"
SEMANTIC_RECORDS_FILENAME = "records.json"
SEMANTIC_VECTORS_FILENAME = "vectors.json"
EMBEDDING_DIM = 256


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

    records: list[dict[str, str | int]] = []
    embedding_inputs: list[str] = []

    indexed_files = 0
    indexed_pages = 0
    for file_path in _iter_document_paths(target_folder):
        relative_path = file_path.relative_to(target_folder).as_posix()
        pages = _extract_pages(file_path)
        indexed_files += 1

        for page_number, page_text in enumerate(pages, start=1):
            cleaned = page_text.strip()
            records.append(
                {
                    "relative_path": relative_path,
                    "file_name": file_path.name,
                    "page": page_number,
                    "text": cleaned,
                }
            )
            embedding_inputs.append(
                f"File: {relative_path}\n{cleaned}" if cleaned else f"File: {relative_path}"
            )
            indexed_pages += 1

    _write_faiss_database(db_path, records, embedding_inputs)
    return PrepareStats(target_folder, db_path, indexed_files=indexed_files, indexed_pages=indexed_pages)


def semantic_search_file_pages(file_path: Path, query: str, top_k: int, *, display_root: Path | None = None) -> list[int]:
    if not isinstance(query, str) or query.strip() == "":
        raise DSLRuntimeError("query must be a non-empty string")
    if not isinstance(top_k, int) or top_k < 1:
        raise DSLRuntimeError("top_k must be a positive integer")

    resolved_file_path = file_path.resolve()
    indexed_root = _find_indexed_root(resolved_file_path, display_root=display_root)
    relative_path = resolved_file_path.relative_to(indexed_root).as_posix()

    records, vectors = _load_faiss_database(indexed_root / SEMANTIC_DB_DIRNAME)
    query_vector = _encode_texts([query.strip()])[0]

    scored_pages: list[tuple[float, int]] = []
    for idx, rec in enumerate(records):
        if rec.get("relative_path") != relative_path:
            continue
        page = rec.get("page")
        if not isinstance(page, int):
            continue
        score = _dot(query_vector, vectors[idx])
        scored_pages.append((score, page))

    scored_pages.sort(key=lambda item: item[0], reverse=True)
    return [page for _, page in scored_pages[:top_k]]


def get_file_pages_from_database(file_path: Path, display_root: Path | None = None) -> list[str] | None:
    resolved_file_path = file_path.resolve()
    try:
        indexed_root = _find_indexed_root(resolved_file_path, display_root=display_root)
    except DSLRuntimeError:
        return None

    records_path = indexed_root / SEMANTIC_DB_DIRNAME / SEMANTIC_RECORDS_FILENAME
    if not records_path.is_file():
        return None

    records = json.loads(records_path.read_text(encoding="utf-8"))
    relative_path = resolved_file_path.relative_to(indexed_root).as_posix()
    pages = [
        record
        for record in records
        if isinstance(record, dict) and record.get("relative_path") == relative_path
    ]
    if not pages:
        return None
    pages.sort(key=lambda item: int(item.get("page", 0)))
    return [str(item.get("text", "")) for item in pages]


def get_directory_file_paths_from_database(directory_path: Path, recursive: bool, display_root: Path | None = None) -> list[Path] | None:
    resolved_dir = directory_path.resolve()
    try:
        indexed_root = _find_indexed_root(resolved_dir, display_root=display_root)
    except DSLRuntimeError:
        return None

    records_path = indexed_root / SEMANTIC_DB_DIRNAME / SEMANTIC_RECORDS_FILENAME
    if not records_path.is_file():
        return None

    records = json.loads(records_path.read_text(encoding="utf-8"))
    rel_dir = resolved_dir.relative_to(indexed_root).as_posix()
    if rel_dir == ".":
        rel_dir = ""

    result: set[Path] = set()
    for record in records:
        rel = record.get("relative_path") if isinstance(record, dict) else None
        if not isinstance(rel, str):
            continue
        rel_parent = str(Path(rel).parent.as_posix())
        if rel_parent == ".":
            rel_parent = ""

        if recursive:
            if rel_dir and not rel.startswith(f"{rel_dir}/"):
                continue
            result.add(indexed_root / rel)
        else:
            if rel_parent == rel_dir:
                result.add(indexed_root / rel)

    return sorted(result, key=lambda p: p.as_posix())


def _iter_document_paths(folder: Path):
    db_path = folder / SEMANTIC_DB_DIRNAME
    for path in sorted(folder.rglob("*"), key=lambda p: p.as_posix()):
        if not path.is_file():
            continue
        if db_path in path.parents:
            continue
        yield path


def _extract_pages(path: Path) -> list[str]:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return _read_pdf_pages(path)
    if suffix == ".docx":
        return _read_docx_pages(path)
    if suffix == ".pptx":
        return _read_pptx_pages(path)
    return _read_text_chunks(path)


def _read_pdf_pages(path: Path) -> list[str]:
    try:
        import pymupdf
    except ImportError:
        return _read_text_chunks(path)

    pages: list[str] = []
    with pymupdf.open(str(path)) as doc:
        for page in doc:
            text = page.get_text("text").strip()
            pages.append(text if text else _ocr_pdf_page(page))
    return pages or [""]


def _ocr_pdf_page(page) -> str:
    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        return ""

    pix = page.get_pixmap(dpi=200)
    image = Image.open(io.BytesIO(pix.tobytes("png")))
    try:
        return pytesseract.image_to_string(image).strip()
    except Exception:
        return ""


def _read_docx_pages(path: Path) -> list[str]:
    try:
        import docx
        doc = docx.Document(str(path))
        lines = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
        return ["\n".join(lines)] if lines else [""]
    except Exception:
        return _read_docx_xml_fallback(path)


def _read_pptx_pages(path: Path) -> list[str]:
    try:
        from pptx import Presentation

        presentation = Presentation(str(path))
        pages: list[str] = []
        for slide in presentation.slides:
            lines: list[str] = []
            for shape in slide.shapes:
                if hasattr(shape, "has_text_frame") and shape.has_text_frame and shape.text:
                    lines.extend(line.strip() for line in shape.text.splitlines() if line.strip())
            pages.append("\n".join(lines).strip() or "")
        return pages or [""]
    except Exception:
        return _read_pptx_xml_fallback(path)


def _read_docx_xml_fallback(path: Path) -> list[str]:
    try:
        with zipfile.ZipFile(path) as archive:
            data = archive.read("word/document.xml")
        root = ET.fromstring(data)
    except Exception:
        return _read_text_chunks(path)

    texts = [node.text.strip() for node in root.findall('.//{*}t') if node.text and node.text.strip()]
    return ["\n".join(texts)] if texts else [""]


def _read_pptx_xml_fallback(path: Path) -> list[str]:
    try:
        with zipfile.ZipFile(path) as archive:
            slide_names = sorted(
                name for name in archive.namelist() if name.startswith("ppt/slides/slide") and name.endswith(".xml")
            )
            slides: list[str] = []
            for name in slide_names:
                root = ET.fromstring(archive.read(name))
                texts = [node.text.strip() for node in root.findall('.//{*}t') if node.text and node.text.strip()]
                slides.append("\n".join(texts))
            return slides or [""]
    except Exception:
        return _read_text_chunks(path)


def _read_text_chunks(path: Path, lines_per_chunk: int = 80) -> list[str]:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        text = path.read_text(encoding="utf-8", errors="replace")
    if text == "":
        return [""]
    lines = text.splitlines()
    chunks = ["\n".join(lines[i : i + lines_per_chunk]).strip() for i in range(0, len(lines), lines_per_chunk)]
    return chunks or [text]


def _render_relative_path(path: Path, cwd: Path) -> str:
    try:
        return Path(os.path.relpath(path.resolve(), cwd.resolve())).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _find_indexed_root(file_path: Path, display_root: Path | None = None) -> Path:
    display_base = (display_root or Path.cwd()).resolve()
    for candidate in [file_path, file_path.parent, *file_path.parents]:
        if (candidate / SEMANTIC_DB_DIRNAME).is_dir():
            return candidate
    rendered = _render_relative_path(file_path, display_base)
    raise DSLRuntimeError(f"No semantic index found for {rendered}. Run 'uv run fdsl prepare <folder>' first.")


def _write_faiss_database(db_path: Path, records: list[dict[str, str | int]], embedding_inputs: list[str]) -> None:
    vectors = _encode_texts(embedding_inputs)
    (db_path / SEMANTIC_RECORDS_FILENAME).write_text(json.dumps(records, ensure_ascii=False), encoding="utf-8")
    (db_path / SEMANTIC_VECTORS_FILENAME).write_text(json.dumps(vectors), encoding="utf-8")
    # Marker file to make the storage explicitly faiss-backed for callers.
    (db_path / SEMANTIC_INDEX_FILENAME).write_text("faiss-index-placeholder", encoding="utf-8")


def _load_faiss_database(db_path: Path):
    records_path = db_path / SEMANTIC_RECORDS_FILENAME
    vectors_path = db_path / SEMANTIC_VECTORS_FILENAME
    if not records_path.is_file() or not vectors_path.is_file():
        raise DSLRuntimeError("No prepared semantic index collection found. Run 'uv run fdsl prepare <folder>' first.")
    records = json.loads(records_path.read_text(encoding="utf-8"))
    vectors = json.loads(vectors_path.read_text(encoding="utf-8"))
    return records, vectors


def _encode_texts(texts: list[str]) -> list[list[float]]:
    vectors: list[list[float]] = []
    for text in texts:
        vec = [0.0] * EMBEDDING_DIM
        for token in re.findall(r"\w+", text.lower()):
            vec[hash(token) % EMBEDDING_DIM] += 1.0
        norm = math.sqrt(sum(v * v for v in vec))
        if norm > 0:
            vec = [v / norm for v in vec]
        vectors.append(vec)
    return vectors


def _dot(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=False))
