from fastapi import APIRouter, Body
from fastapi.responses import JSONResponse

from ..controllers.auth_controller import login_controller, register_controller

router = APIRouter()


@router.post("/register")
async def register(payload: dict = Body(...)) -> dict:
    """POST /v1/auth/register: Register a user and return auth token payload."""
    status_code, body = register_controller(payload)
    return JSONResponse(status_code=status_code, content=body)


@router.post("/login")
async def login(payload: dict = Body(...)) -> dict:
    """POST /v1/auth/login: Authenticate by email/password and return auth token payload."""
    status_code, body = login_controller(payload)
    return JSONResponse(status_code=status_code, content=body)
