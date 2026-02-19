from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from filesdsl.interpreter import run_script
from filesdsl.semantic import prepare_semantic_database


class PrepareFaissIntegrationTests(unittest.TestCase):
    def test_prepare_data_and_db_backed_file_directory_ops(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            work = Path(temp_dir) / 'data'
            work.mkdir(parents=True, exist_ok=True)
            self._create_fixture_documents(work)

            stats = prepare_semantic_database(work)
            self.assertEqual(stats.db_path.name, '.fdsl_faiss')
            self.assertGreaterEqual(stats.indexed_files, 4)
            self.assertGreaterEqual(stats.indexed_pages, 4)

            # Ensure file methods read from the DB by removing source files after prepare.
            for path in work.rglob('*'):
                if path.is_file() and '.fdsl_faiss' not in path.as_posix():
                    path.unlink()

            script = '''
root = Directory('.')
all_files = root.search('sample|notes', scope='name')
count = len(all_files)
notes = File('notes.txt')
has_alpha = notes.contains('alpha')
alpha_pages = notes.search('alpha')
head_text = notes.head()
'''
            variables = run_script(script, cwd=work, sandbox_root=work)
            self.assertGreaterEqual(variables['count'], 1)
            self.assertTrue(variables['has_alpha'])
            self.assertEqual(variables['alpha_pages'], [1])
            self.assertIn('alpha', variables['head_text'])

    def _create_fixture_documents(self, root: Path) -> None:
        (root / 'notes.txt').write_text('alpha line\nbeta line\n', encoding='utf-8')

        pdf_content = '''%PDF-1.4
1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj
2 0 obj << /Type /Pages /Count 1 /Kids [3 0 R] >> endobj
3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 300 300] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >> endobj
4 0 obj << /Length 55 >> stream
BT /F1 18 Tf 72 220 Td (alpha pdf content) Tj ET
endstream endobj
5 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj
xref
0 6
0000000000 65535 f 
0000000010 00000 n 
0000000062 00000 n 
0000000121 00000 n 
0000000257 00000 n 
0000000365 00000 n 
trailer << /Root 1 0 R /Size 6 >>
startxref
435
%%EOF
'''
        (root / 'sample.pdf').write_text(pdf_content, encoding='latin-1')

        with ZipFile(root / 'sample.docx', 'w', ZIP_DEFLATED) as archive:
            archive.writestr('[Content_Types].xml', '''<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>''')
            archive.writestr('_rels/.rels', '''<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>''')
            archive.writestr('word/document.xml', '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>
<w:p><w:r><w:t>alpha in fake docx</w:t></w:r></w:p>
<w:p><w:r><w:t>beta in fake docx</w:t></w:r></w:p>
</w:body></w:document>''')

        with ZipFile(root / 'sample.pptx', 'w', ZIP_DEFLATED) as archive:
            archive.writestr('[Content_Types].xml', '''<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>
<Override PartName="/ppt/slides/slide1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>
</Types>''')
            archive.writestr('_rels/.rels', '''<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="ppt/presentation.xml"/>
</Relationships>''')
            archive.writestr('ppt/presentation.xml', '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:presentation xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
<p:sldIdLst><p:sldId id="256" r:id="rId1"/></p:sldIdLst></p:presentation>''')
            archive.writestr('ppt/_rels/presentation.xml.rels', '''<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide1.xml"/>
</Relationships>''')
            archive.writestr('ppt/slides/slide1.xml', '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
<p:cSld><p:spTree><p:sp><p:txBody><a:p><a:r><a:t>alpha in fake pptx</a:t></a:r></a:p></p:txBody></p:sp></p:spTree></p:cSld></p:sld>''')


if __name__ == '__main__':
    unittest.main()
