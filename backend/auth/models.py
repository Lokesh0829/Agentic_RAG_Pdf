"""
auth/models.py — User document schemas
"""
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field
from bson import ObjectId


class UserCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=6)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: str
    name: str
    email: str
    created_at: datetime

    @classmethod
    def from_mongo(cls, doc: dict) -> "UserOut":
        return cls(
            id=str(doc["_id"]),
            name=doc["name"],
            email=doc["email"],
            created_at=doc["created_at"],
        )


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
