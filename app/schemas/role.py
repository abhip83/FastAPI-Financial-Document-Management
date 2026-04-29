from pydantic import BaseModel, ConfigDict


class RoleOut(BaseModel):
    id: int
    name: str

    model_config = ConfigDict(from_attributes=True)
