from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite:///./financial_documents.db"
    jwt_secret_key: str = "3caaa6db3c520d236018881b5bf0b2c9b08a7e28eb7922864e8bb3c76e404781"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    uploads_dir: Path = Path("uploads")
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "financial_document_chunks"
    qdrant_api_key: str | None = None

    embedding_model_name: str = "all-MiniLM-L6-v2"
    sample_admin_email: str = "admin@example.com"
    sample_admin_password: str = "Admin@123"

    class Config:
        env_file = ".env"


settings = Settings()
settings.uploads_dir.mkdir(parents=True, exist_ok=True)
