"""Golden fixture: FastAPI-style routes and router prefixes."""
from fastapi import APIRouter

from external import api_router

router = APIRouter(prefix="/users", tags=["users"])
bare = APIRouter()


@router.post("/signup", response_model=UserPublic)
def register_user(payload: UserRegister):
    """Create a user."""
    return create_user(payload)


@router.get("/")
def read_users():
    return []


@bare.delete("/cache")
def clear_cache():
    return True


@api_router.get("/health")
def health():
    return "ok"
