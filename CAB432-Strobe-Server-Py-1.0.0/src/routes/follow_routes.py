from fastapi import APIRouter, Depends, Path
from fastapi.responses import JSONResponse

from ..controllers.follow_controller import (
    follow_user_controller,
    get_followers_controller,
    get_following_controller,
    unfollow_user_controller,
)
from ..middleware.auth import authenticate, optional_authenticate

router = APIRouter()


@router.post("/follow")
async def follow(user_id: str = Path(...), current_user: dict = Depends(authenticate)) -> dict:
    """POST /v1/users/{user_id}/follow: Follow the target user as the authenticated caller."""
    status_code, body = follow_user_controller(current_user["userId"], user_id)
    return JSONResponse(status_code=status_code, content=body)


@router.delete("/follow")
async def unfollow(user_id: str = Path(...), current_user: dict = Depends(authenticate)) -> dict:
    """DELETE /v1/users/{user_id}/follow: Unfollow the target user as the authenticated caller."""
    status_code, body = unfollow_user_controller(current_user["userId"], user_id)
    return JSONResponse(status_code=status_code, content=body)


@router.get("/followers")
async def followers(user_id: str = Path(...), current_user: dict | None = Depends(optional_authenticate)) -> dict:
    """GET /v1/users/{user_id}/followers: Return followers list for target user."""
    status_code, body = get_followers_controller(user_id, current_user["userId"] if current_user else None)
    return JSONResponse(status_code=status_code, content=body)


@router.get("/following")
async def following(user_id: str = Path(...), current_user: dict | None = Depends(optional_authenticate)) -> dict:
    """GET /v1/users/{user_id}/following: Return following list for target user."""
    status_code, body = get_following_controller(user_id, current_user["userId"] if current_user else None)
    return JSONResponse(status_code=status_code, content=body)
