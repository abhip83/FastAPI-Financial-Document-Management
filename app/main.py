import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.db.database import Base, engine, SessionLocal
from app.models import user, role, document
from app.routes import auth, documents, rag
from app.services.auth_service import ensure_default_roles_and_admin

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        ensure_default_roles_and_admin(db)
        logger.info("Application startup completed")
    finally:
        db.close()
    yield


app = FastAPI(
    title="Financial Document Management System with RAG",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(auth.router)
app.include_router(documents.router)
app.include_router(rag.router)


@app.get("/")
def health_check():
    return {"status": "ok"}
