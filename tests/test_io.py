import zipfile

import pandas as pd

from src.document import Document
from src.io.readers import read_excel_chunks, read_zip_chunks


def test_read_excel_chunks(tmp_path):
    xl = tmp_path / "sheet.xlsx"
    pd.DataFrame({"Name": ["Anna"], "Age": [40]}).to_excel(xl, index=False)
    chunks = list(read_excel_chunks(xl))
    assert len(chunks) == 1
    assert list(chunks[0].columns) == ["Name", "Age"]
    assert len(chunks[0]) == 1


def test_read_zip_with_xlsx(tmp_path):
    xl = tmp_path / "sheet.xlsx"
    pd.DataFrame({"Name": ["Anna"], "Age": [40]}).to_excel(xl, index=False)
    zp = tmp_path / "bundle.zip"
    with zipfile.ZipFile(zp, "w") as z:
        z.write(xl, arcname="sheet.xlsx")
    chunks = list(read_zip_chunks(zp))
    assert len(chunks) == 1
    assert list(chunks[0].columns) == ["Name", "Age"]


def test_document_from_zip_xlsx(tmp_path):
    xl = tmp_path / "sheet.xlsx"
    pd.DataFrame({"Name": ["Anna"], "Age": [40]}).to_excel(xl, index=False)
    zp = tmp_path / "bundle.zip"
    with zipfile.ZipFile(zp, "w") as z:
        z.write(xl, arcname="sheet.xlsx")
    doc = Document.from_file(zp)
    assert doc.shape == (1, 2)


def test_pdf_export_embeds_dejavu(tmp_path):
    doc = Document.from_dict([{"Имя": "Привет", "Возраст": "30"}])
    out = tmp_path / "out.pdf"
    doc.export("pdf", output_path=out)
    data = out.read_bytes()
    assert b"DejaVu" in data
