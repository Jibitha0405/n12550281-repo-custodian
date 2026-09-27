from fastapi import APIRouter, Body, Depends, Query
from fastapi.responses import JSONResponse

from ..controllers.post_controller import (
    create_post_controller,
    delete_post_controller,
    get_post_controller,
    get_user_posts_controller,
    hide_post_controller,
    like_post_controller,
    unlike_post_controller,
    update_post_controller,
)
from ..middleware.auth import authenticate, optional_authenticate, require_moderator

router = APIRouter()


@router.post("")
async def create(payload: dict = Body(...), current_user: dict = Depends(authenticate)) -> dict:
    """POST /v1/posts: Create a post for the authenticated user."""
    status_code, body = create_post_controller(current_user["userId"], payload)
    return JSONResponse(status_code=status_code, content=body)


@router.get("/user/{user_id}")
async def list_user_posts(user_id: str, limit: int = Query(default=20), offset: int = Query(default=0), current_user: dict | None = Depends(optional_authenticate)) -> dict:
    """GET /v1/posts/user/{user_id}: List posts for a specific user."""
    user_id_current = current_user["userId"] if current_user else None
    user_role = current_user["userRole"] if current_user else None
    status_code, body = get_user_posts_controller(user_id, limit, offset, user_id_current, user_role)
    return JSONResponse(status_code=status_code, content=body)


@router.get("/{id}")
async def get_single_post(id: str, current_user: dict | None = Depends(optional_authenticate)) -> dict:
    """GET /v1/posts/{id}: Fetch one post by ID."""
    user_id = current_user["userId"] if current_user else None
    user_role = current_user["userRole"] if current_user else None
    status_code, body = get_post_controller(id, user_id, user_role)
    return JSONResponse(status_code=status_code, content=body)


@router.put("/{id}")
async def update_single_post(id: str, payload: dict = Body(...), current_user: dict = Depends(authenticate)) -> dict:
    """PUT /v1/posts/{id}: Update one post owned by the authenticated user."""
    status_code, body = update_post_controller(id, current_user["userId"], payload)
    return JSONResponse(status_code=status_code, content=body)


@router.delete("/{id}")
async def remove_post(id: str, current_user: dict = Depends(authenticate)) -> dict:
    """DELETE /v1/posts/{id}: Delete one post owned by the authenticated user."""
    status_code, body = delete_post_controller(id, current_user["userId"])
    return JSONResponse(status_code=status_code, content=body)


@router.post("/{id}/like")
async def create_like(id: str, current_user: dict = Depends(authenticate)) -> dict:
    """POST /v1/posts/{id}/like: Like a post as the authenticated user."""
    status_code, body = like_post_controller(id, current_user["userId"])
    return JSONResponse(status_code=status_code, content=body)


@router.delete("/{id}/like")
async def remove_like(id: str, current_user: dict = Depends(authenticate)) -> dict:
    """DELETE /v1/posts/{id}/like: Remove the authenticated user's like from a post."""
    status_code, body = unlike_post_controller(id, current_user["userId"])
    return JSONResponse(status_code=status_code, content=body)


@router.post("/{id}/hide")
async def hide_single_post(id: str, current_user: dict = Depends(require_moderator)) -> dict:
    """POST /v1/posts/{id}/hide: Moderator-only post hide action."""
    status_code, body = hide_post_controller(id, current_user["userId"], current_user["userRole"])
    return JSONResponse(status_code=status_code, content=body)
