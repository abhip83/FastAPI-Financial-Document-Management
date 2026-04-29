from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


DocumentType = Literal["invoice", "report", "contract"]


class DocumentCreate(BaseModel):
    title: str
    company_name: str
    document_type: DocumentType


class DocumentOut(BaseModel):
    id: int
    title: str
    company_name: str
    document_type: str
    uploaded_by: int
    created_at: datetime
    file_path: str

    model_config = ConfigDict(from_attributes=True)


class RagIndexRequest(BaseModel):
    document_id: int


class RagSearchRequest(BaseModel):
    query: str


class RagChunk(BaseModel):
    text: str
    document_id: int
    score: float


class RagSearchResponse(BaseModel):
    results: list[RagChunk]
