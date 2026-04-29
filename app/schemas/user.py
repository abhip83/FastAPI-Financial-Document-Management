from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.schemas.role import RoleOut


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=100)
    password: str = Field(min_length=6, max_length=128)
    role_name: str = "Client"


class UserOut(BaseModel):
    id: int
    email: EmailStr
    full_name: str
    role: RoleOut

    model_config = ConfigDict(from_attributes=True)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
