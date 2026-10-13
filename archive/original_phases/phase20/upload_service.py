import os

import pandas as pd


# ============================================================
# SUPPORTED EXTENSIONS
# ============================================================

ALLOWED_EXTENSIONS = {
    ".csv",
    ".xlsx",
    ".xls",
    ".pdf"
}


# ============================================================
# VALIDATE EXTENSION
# ============================================================

def validate_file_extension(filename):

    if not filename:

        raise ValueError(
            "Filename is missing."
        )

    extension = os.path.splitext(
        filename
    )[1].lower()

    if extension not in ALLOWED_EXTENSIONS:

        raise ValueError(
            "Unsupported file type. "
            "Allowed formats: CSV, XLSX, XLS, PDF."
        )

    return extension


# ============================================================
# CSV
# ============================================================

def read_csv_file(file_path):

    return pd.read_csv(
        file_path
    )


# ============================================================
# EXCEL
# ============================================================

def read_excel_file(file_path):

    return pd.read_excel(
        file_path
    )


# ============================================================
# PDF
# ============================================================

def read_pdf_file(file_path):

    try:

        import pdfplumber

    except ImportError:

        raise ValueError(
            "PDF support requires pdfplumber. "
            "Run: pip install pdfplumber"
        )

    tables = []

    with pdfplumber.open(
        file_path
    ) as pdf:

        for page in pdf.pages:

            page_tables = (
                page.extract_tables()
            )

            for table in page_tables:

                if not table:
                    continue

                if len(table) < 2:
                    continue

                header = table[0]

                rows = table[1:]

                cleaned_header = []

                for index, column in enumerate(
                    header
                ):

                    if (
                        column is None
                        or
                        str(column).strip() == ""
                    ):

                        cleaned_header.append(
                            f"column_{index + 1}"
                        )

                    else:

                        cleaned_header.append(
                            str(column).strip()
                        )

                dataframe = pd.DataFrame(
                    rows,
                    columns=cleaned_header
                )

                tables.append(
                    dataframe
                )

    if not tables:

        raise ValueError(
            "No structured table was found "
            "inside the PDF."
        )

    dataframe = pd.concat(
        tables,
        ignore_index=True
    )

    return dataframe


# ============================================================
# MAIN READER
# ============================================================

def read_uploaded_file(file_path):

    extension = validate_file_extension(
        file_path
    )

    if extension == ".csv":

        dataframe = read_csv_file(
            file_path
        )

    elif extension in [
        ".xlsx",
        ".xls"
    ]:

        dataframe = read_excel_file(
            file_path
        )

    elif extension == ".pdf":

        dataframe = read_pdf_file(
            file_path
        )

    else:

        raise ValueError(
            "Unsupported file format."
        )


    # ========================================================
    # BASIC CLEANING
    # ========================================================

    if dataframe.empty:

        raise ValueError(
            "The uploaded file contains no data."
        )


    dataframe = dataframe.dropna(
        how="all"
    )


    dataframe = dataframe.dropna(
        axis=1,
        how="all"
    )


    dataframe.columns = [
        str(column).strip()
        for column in dataframe.columns
    ]


    return dataframe