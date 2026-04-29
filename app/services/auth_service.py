from fastapi import Depends, HTTPException, status
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.config import settings
from app.db.database import get_db
from app.models.role import Role
from app.models.user import User
from app.schemas.user import UserCreate
from app.utils.jwt import get_current_user

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
DEFAULT_ROLES = ["Admin", "Analyst", "Auditor", "Client"]


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def ensure_default_roles_and_admin(db: Session) -> None:
    for role_name in DEFAULT_ROLES:
        if not db.query(Role).filter(Role.name == role_name).first():
            db.add(Role(name=role_name))
    db.commit()

    admin_role = db.query(Role).filter(Role.name == "Admin").first()
    admin = db.query(User).filter(User.email == settings.sample_admin_email).first()
    if not admin and admin_role:
        db.add(
            User(
                email=settings.sample_admin_email,
                full_name="Sample Admin",
                hashed_password=hash_password(settings.sample_admin_password),
                role_id=admin_role.id,
            )
        )
        db.commit()


def create_user(db: Session, payload: UserCreate) -> User:
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    role = db.query(Role).filter(Role.name == payload.role_name).first()
    if not role:
        raise HTTPException(status_code=400, detail="Invalid role")

    user = User(
        email=payload.email,
        full_name=payload.full_name,
        hashed_password=hash_password(payload.password),
        role_id=role.id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, email: str, password: str) -> User:
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def require_roles(*allowed_roles: str):
    def dependency(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role.name not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return current_user

    return dependency
