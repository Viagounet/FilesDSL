from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from filesdsl.errors import DSLRuntimeError, DSLSyntaxError
from filesdsl.interpreter import run_script


class FilesDSLTests(unittest.TestCase):
    def test_range_syntax_in_lists(self) -> None:
        script = "pages = [1, 5:8, 15]\n"
        variables = run_script(script, cwd=Path.cwd(), sandbox_root=Path.cwd())
        self.assertEqual(variables["pages"], [1, 5, 6, 7, 8, 15])

    def test_directory_search_and_file_api(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "a.txt").write_text("alpha\nbeta\ngamma\n", encoding="utf-8")
            (root / "b.txt").write_text("delta\n", encoding="utf-8")
            (root / "nested").mkdir()
            (root / "nested" / "c.txt").write_text("alpha inside nested\n", encoding="utf-8")

            script = """
docs = Directory(".")
matches = docs.search("a\\.txt$", scope="name")
hits = []
for file in matches:
    if file.contains("alpha"):
        pages = file.search("alpha")
        chunks = file.read(pages=[1])
        first = file.head()
        last = file.tail()
        hits = hits + pages
"""
            variables = run_script(script, cwd=root, sandbox_root=root)
            self.assertEqual(variables["hits"], [1])
            self.assertEqual(len(variables["chunks"]), 1)
            self.assertTrue("alpha" in variables["first"])
            self.assertTrue("gamma" in variables["last"])

            recursive_script = """
docs = Directory(".")
nested = docs.search("c\\.txt$", scope="name")
count = len(nested)
"""
            recursive_vars = run_script(recursive_script, cwd=root, sandbox_root=root)
            self.assertEqual(recursive_vars["count"], 1)

    def test_sandbox_denies_outside_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            script = "docs = Directory('/')\n"
            with self.assertRaises(DSLRuntimeError):
                run_script(script, cwd=root, sandbox_root=root)

    def test_table_returns_tree_string(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "toc.txt").write_text(
                "1 Introduction ........ 1\n"
                "1.1 Scope ........ 2\n"
                "2 Methods ........ 5\n",
                encoding="utf-8",
            )
            script = """
docs = Directory(".")
files = docs.search("toc\\.txt$", scope="name")
toc = ""
for file in files:
    toc = file.table()
"""
            variables = run_script(script, cwd=root, sandbox_root=root)
            self.assertIsInstance(variables["toc"], str)
            self.assertIn("1 Introduction (p.1)", variables["toc"])
            self.assertIn("  1.1 Scope (p.2)", variables["toc"])
            self.assertIn("2 Methods (p.5)", variables["toc"])

    def test_table_returns_no_toc_message(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            no_toc_file = root / "plain.txt"
            no_toc_file.write_text("hello\nworld\n", encoding="utf-8")
            script = """
docs = Directory(".")
files = docs.search("plain\\.txt$", scope="name")
toc = ""
for file in files:
    toc = file.table()
"""
            variables = run_script(script, cwd=root, sandbox_root=root)
            expected = f"No table of contents detected for {no_toc_file.as_posix()}"
            self.assertEqual(variables["toc"], expected)

    def test_syntax_error_reports_location(self) -> None:
        script = "for file in Directory('.')\n    print(file)\n"
        with self.assertRaises(DSLSyntaxError) as context:
            run_script(script, cwd=Path.cwd(), sandbox_root=Path.cwd())
        self.assertEqual(context.exception.line, 1)
        self.assertGreaterEqual(context.exception.column, 1)


if __name__ == "__main__":
    unittest.main()
