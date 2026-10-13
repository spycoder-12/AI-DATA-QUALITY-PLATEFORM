from pathlib import Path

from fastapi import UploadFile

from app.config import (
    UPLOAD_DIR,
    ALLOWED_EXTENSIONS
)


def validate_file(
    filename: str
) -> bool:

    extension = (
        Path(filename)
        .suffix
        .lower()
    )

    return extension in (
        ALLOWED_EXTENSIONS
    )


async def save_upload(
    file: UploadFile
) -> Path:

    if not file.filename:

        raise ValueError(
            "Filename is missing."
        )

    if not validate_file(
        file.filename
    ):

        raise ValueError(
            "Only CSV files are supported."
        )

    destination = (
        UPLOAD_DIR /
        file.filename
    )

    content = await file.read()

    with open(
        destination,
        "wb"
    ) as output:

        output.write(content)

    return destination