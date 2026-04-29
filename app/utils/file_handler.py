from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile

from app.config import settings


def save_upload_file(file: UploadFile) -> Path:
    filename = file.filename or ""
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")

    destination = settings.uploads_dir / f"{uuid4().hex}_{Path(filename).name}"
    with destination.open("wb") as buffer:
        while chunk := file.file.read(1024 * 1024):
            buffer.write(chunk)
    return destination


def delete_file(path: Path) -> None:
    if path.exists() and path.is_file():
        path.unlink()
