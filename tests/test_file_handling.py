"""Upload validation, safe storage and dataset loading."""
import io

import numpy as np
import pandas as pd
import pytest

from app.utils.file_handler import load_dataset
from app.utils.validators import AppError, sanitize_filename, validate_extension
from tests.conftest import csv_bytes, make_df


def upload(client, name, content, mime="text/csv"):
    return client.post("/api/datasets/upload", files={"file": (name, content, mime)})


def test_csv_upload_success(client, clean_df):
    r = upload(client, "data.csv", csv_bytes(clean_df))
    assert r.status_code == 201
    j = r.json()
    assert j["validation"]["rows"] == 300 and j["validation"]["status"] == "VALID"
    assert len(j["preview"]["rows"]) == 10 and j["dataset"]["file_type"] == "csv"


def test_original_file_preserved_byte_for_byte(client, clean_df):
    content = csv_bytes(clean_df)
    ds = upload(client, "data.csv", content).json()["dataset"]
    stored = list(client.settings.upload_dir.iterdir())
    assert len(stored) == 1 and stored[0].read_bytes() == content
    assert client.get(f"/api/datasets/{ds['id']}/download").content == content


def test_filename_sanitised_and_path_traversal_blocked(client, clean_df):
    r = upload(client, "../../etc/passwd.csv", csv_bytes(clean_df))
    assert r.status_code == 201 and r.json()["dataset"]["name"] == "passwd.csv"
    stored = [p.name for p in client.settings.upload_dir.iterdir()]
    assert all(len(n) == 36 and n.endswith(".csv") for n in stored)       # uuid hex + ext
    assert not (client.settings.base_dir.parent / "etc").exists()


def test_sanitize_filename_unit():
    assert sanitize_filename("C:\\Users\\me\\a b.csv") == "a b.csv"
    with pytest.raises(AppError):
        sanitize_filename("...")


@pytest.mark.parametrize("name", ["malware.exe", "data.txt", "archive.zip", "noext"])
def test_unsupported_extensions_rejected(client, name):
    r = upload(client, name, b"abc")
    assert r.status_code == 400 and r.json()["error"]["code"] in {"unsupported_type"}


def test_size_limit_enforced(client):
    big = b"a,b\n" + b"1,2\n" * (700_000)                 # > 2 MB limit from fixture
    r = upload(client, "big.csv", big)
    assert r.status_code == 413 and "too large" in r.json()["error"]["message"].lower()
    assert list(client.settings.upload_dir.iterdir()) == []         # nothing left behind


def test_empty_file_and_header_only(client):
    assert upload(client, "e.csv", b"").status_code == 400
    r = upload(client, "h.csv", b"a,b,c\n")
    assert r.status_code == 400 and r.json()["error"]["code"] == "empty_dataset"
    assert list(client.settings.upload_dir.iterdir()) == []         # rejected uploads are removed


def test_binary_garbage_csv_rejected(client):
    r = upload(client, "x.csv", bytes(range(256)) * 20)
    assert r.status_code == 400 and r.json()["error"]["code"] == "invalid_csv"


def test_corrupted_csv_rows_skipped_with_warning(tmp_path):
    p = tmp_path / "bad.csv"
    p.write_text("a,b,c\n1,2,3\n4,5,6,7,8\n9,10,11\n")
    df, meta = load_dataset(p)
    assert len(df) == 2 and any("malformed" in w.lower() for w in meta["warnings"])


def test_invalid_excel_rejected(client):
    r = upload(client, "fake.xlsx", b"this is not a workbook")
    assert r.status_code == 400 and r.json()["error"]["code"] == "invalid_excel"
    zipish = upload(client, "fake2.xlsx", b"PK\x03\x04" + b"garbage" * 50)
    assert zipish.status_code == 400 and zipish.json()["error"]["code"] == "invalid_excel"


def test_xlsx_and_xls_upload(client, clean_df, tmp_path):
    buf = io.BytesIO()
    clean_df.to_excel(buf, index=False, engine="openpyxl")
    r = upload(client, "book.xlsx", buf.getvalue(), "application/vnd.ms-excel")
    assert r.status_code == 201 and r.json()["validation"]["rows"] == 300
    import xlwt
    wb = xlwt.Workbook(); ws = wb.add_sheet("s")
    for j, c in enumerate(["a", "b"]):
        ws.write(0, j, c)
    for i in range(1, 11):
        ws.write(i, 0, i); ws.write(i, 1, i * 2.5)
    out = io.BytesIO(); wb.save(out)
    r = upload(client, "old.xls", out.getvalue(), "application/vnd.ms-excel")
    assert r.status_code == 201 and r.json()["validation"]["rows"] == 10


def test_pdf_table_extraction(client):
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
    buf = io.BytesIO()
    data = [["name", "age", "income"]] + [[f"P{i}", 20 + i, 1000 * i] for i in range(1, 9)]
    t = Table(data); t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, colors.black)]))
    SimpleDocTemplate(buf).build([t])
    r = upload(client, "table.pdf", buf.getvalue(), "application/pdf")
    assert r.status_code == 201, r.text
    assert r.json()["validation"]["rows"] == 8
    cols = r.json()["validation"]["column_names"]
    assert cols == ["name", "age", "income"]


def test_pdf_without_tables_and_fake_pdf(client):
    from reportlab.pdfgen import canvas
    buf = io.BytesIO(); c = canvas.Canvas(buf); c.drawString(100, 700, "just text, no table"); c.save()
    r = upload(client, "text.pdf", buf.getvalue(), "application/pdf")
    assert r.status_code == 400 and r.json()["error"]["code"] == "unsupported_pdf"
    assert upload(client, "fake.pdf", b"not a pdf").json()["error"]["code"] == "invalid_pdf"


def test_empty_rows_columns_dropped_and_names_normalised(tmp_path):
    p = tmp_path / "m.csv"
    p.write_text("First Name,Total $,Unnamed Empty, 2nd-Col\nA,1,,x\n,,,\nB,2,,y\n  ,  ,  ,  \n")
    df, meta = load_dataset(p)
    assert list(df.columns) == ["first_name", "total", "col_2nd_col"]
    assert len(df) == 2 and meta["dropped_empty_rows"] == 2 and meta["dropped_empty_columns"] == 1
    assert meta["column_map"]["First Name"] == "first_name"


def test_duplicate_column_names_made_unique(tmp_path):
    p = tmp_path / "d.csv"; p.write_text("a,A,a\n1,2,3\n")
    df, _ = load_dataset(p)
    assert len(set(df.columns)) == 3 and all(c.startswith("a") for c in df.columns)   # always unique
    from app.utils.helpers import normalize_columns
    assert normalize_columns(["a", "A", "a"])[0] == ["a", "a_2", "a_3"]


def test_encoding_and_delimiter_detection(tmp_path):
    p = tmp_path / "l1.csv"
    p.write_bytes("nom;ville\nJos\xe9;Z\xfcrich\nAn\xe9;Paris\n".encode("cp1252"))
    df, meta = load_dataset(p)
    assert meta["delimiter"] == ";" and list(df.columns) == ["nom", "ville"]
    assert df["nom"].iloc[0] == "José" and any("Windows-1252" in w for w in meta["warnings"])


def test_numeric_like_text_is_coerced_and_bad_tokens_recorded(tmp_path):
    p = tmp_path / "n.csv"
    vals = [str(i) for i in range(30)] + ["abc"]
    p.write_text("x\n" + "\n".join(vals) + "\n")
    df, meta = load_dataset(p)
    assert pd.api.types.is_numeric_dtype(df["x"])
    assert meta["coerced"]["x"]["count"] == 1 and meta["coerced"]["x"]["examples"] == ["abc"]


def test_dataset_listing_and_delete(client, clean_df):
    ds = upload(client, "a.csv", csv_bytes(clean_df)).json()["dataset"]
    assert client.get("/api/datasets").json()["count"] == 1
    assert client.get(f"/api/datasets/{ds['id']}/preview?rows=3").json()["rows"].__len__() == 3
    assert client.delete(f"/api/datasets/{ds['id']}").status_code == 200
    assert client.get("/api/datasets").json()["count"] == 0
    assert list(client.settings.upload_dir.iterdir()) == []
    assert client.get(f"/api/datasets/{ds['id']}").status_code == 404
