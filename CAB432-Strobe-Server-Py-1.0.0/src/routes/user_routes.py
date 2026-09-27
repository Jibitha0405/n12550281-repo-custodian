from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from ..controllers.user_controller import (
    delete_own_account_controller,
    get_user_profile_controller,
    list_users_controller,
)
from ..middleware.auth import authenticate, optional_authenticate

router = APIRouter()


@router.get("")
async def users(q: str = Query(default=""), limit: int = Query(default=20), current_user: dict | None = Depends(optional_authenticate)) -> dict:
    """GET /v1/users: List users for discovery/search, optionally enriched for authenticated caller."""
    status_code, body = list_users_controller(q, limit, current_user["userId"] if current_user else None)
    return JSONResponse(status_code=status_code, content=body)


@router.get("/{id}")
async def profile(id: str, current_user: dict | None = Depends(optional_authenticate)) -> dict:
    """GET /v1/users/{id}: Return one public user profile."""
    status_code, body = get_user_profile_controller(id, current_user["userId"] if current_user else None)
    return JSONResponse(status_code=status_code, content=body)


@router.delete("/{id}")
async def delete_account(id: str, current_user: dict = Depends(authenticate)) -> dict:
    """DELETE /v1/users/{id}: Delete the authenticated user's own account."""
    status_code, body = delete_own_account_controller(id, current_user["userId"])
    return JSONResponse(status_code=status_code, content=body)
