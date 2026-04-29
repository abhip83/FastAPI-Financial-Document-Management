from pathlib import Path
from typing import Optional

from fastapi import HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.models.document import Document
from app.utils.file_handler import delete_file, save_upload_file


def create_document(
    db: Session,
    file: UploadFile,
    title: str,
    company_name: str,
    document_type: str,
    uploaded_by: int,
) -> Document:
    file_path = save_upload_file(file)
    document = Document(
        title=title,
        company_name=company_name,
        document_type=document_type,
        uploaded_by=uploaded_by,
        file_path=str(file_path),
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


def list_documents(db: Session) -> list[Document]:
    return db.query(Document).order_by(Document.created_at.desc()).all()


def get_document(db: Session, document_id: int) -> Document:
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    return document


def delete_document(db: Session, document_id: int) -> None:
    document = get_document(db, document_id)
    delete_file(Path(document.file_path))
    db.delete(document)
    db.commit()


def search_documents(
    db: Session,
    title: Optional[str] = None,
    company_name: Optional[str] = None,
    document_type: Optional[str] = None,
) -> list[Document]:
    query = db.query(Document)
    if title:
        query = query.filter(Document.title.ilike(f"%{title}%"))
    if company_name:
        query = query.filter(Document.company_name.ilike(f"%{company_name}%"))
    if document_type:
        query = query.filter(Document.document_type == document_type)
    return query.order_by(Document.created_at.desc()).all()
