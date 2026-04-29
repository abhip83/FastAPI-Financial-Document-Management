from typing import Optional

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.user import User
from app.schemas.document import DocumentOut, DocumentType
from app.services.auth_service import require_roles
from app.services.document_service import (
    create_document,
    delete_document,
    get_document,
    list_documents,
    search_documents,
)
from app.utils.jwt import get_current_user

router = APIRouter(prefix="/documents", tags=["Documents"])


@router.post("/upload", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
def upload_document(
    title: str = Form(...),
    company_name: str = Form(...),
    document_type: DocumentType = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Analyst")),
):
    return create_document(db, file, title, company_name, document_type, current_user.id)


@router.get("", response_model=list[DocumentOut])
def get_documents(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return list_documents(db)


@router.get("/search", response_model=list[DocumentOut])
def metadata_search(
    title: Optional[str] = Query(None),
    company_name: Optional[str] = Query(None),
    document_type: Optional[DocumentType] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return search_documents(db, title, company_name, document_type)


@router.get("/{document_id}", response_model=DocumentOut)
def read_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return get_document(db, document_id)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    delete_document(db, document_id)
    return None
