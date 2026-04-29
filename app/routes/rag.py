from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.user import User
from app.schemas.document import RagIndexRequest, RagSearchRequest, RagSearchResponse
from app.services.auth_service import require_roles
from app.services.rag_service import index_document, search_chunks
from app.utils.jwt import get_current_user

router = APIRouter(prefix="/rag", tags=["RAG"])


@router.post("/index-document")
def index_document_endpoint(
    payload: RagIndexRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Analyst")),
):
    indexed_chunks = index_document(db, payload.document_id)
    return {"document_id": payload.document_id, "indexed_chunks": indexed_chunks}


@router.post("/search", response_model=RagSearchResponse)
def rag_search(
    payload: RagSearchRequest,
    current_user: User = Depends(get_current_user),
):
    return RagSearchResponse(results=search_chunks(payload.query))
