from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()

# Mock users DB
users = []

class User(BaseModel):
    uid: str
    email: str
    role: str  # "buyer" or "seller"

@router.post("/register")
async def register_user(user: User):
    users.append(user)
    return {"message": "User registered successfully"}

@router.get("/")
async def list_users():
    return users
