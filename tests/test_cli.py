from __future__ import annotations

import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from filesdsl.__main__ import main
from filesdsl.semantic import PrepareStats


class FilesDSLCLITests(unittest.TestCase):
    def test_prepare_command_invokes_index_builder(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir).resolve()
            stats = PrepareStats(
                folder=folder,
                db_path=folder / ".fdsl_faiss",
                indexed_files=3,
                indexed_pages=9,
            )
            with patch("filesdsl.__main__.prepare_semantic_database", return_value=stats) as prepare_mock:
                output = io.StringIO()
                with redirect_stdout(output):
                    exit_code = main(["prepare", temp_dir])

            self.assertEqual(exit_code, 0)
            prepare_mock.assert_called_once_with(folder)
            text = output.getvalue()
            self.assertIn("Indexed files: 3", text)
            self.assertIn("Indexed pages: 9", text)


if __name__ == "__main__":
    unittest.main()
