from fastapi import APIRouter, Body, Depends, Path
from fastapi.responses import JSONResponse

from ..controllers.comment_controller import (
    create_comment_controller,
    delete_comment_controller,
    get_post_comments_controller,
)
from ..middleware.auth import authenticate, optional_authenticate

router = APIRouter()


@router.post("")
async def create(post_id: str = Path(...), payload: dict = Body(...), current_user: dict = Depends(authenticate)) -> dict:
    """POST /v1/posts/{post_id}/comments: Create a comment for a post."""
    status_code, body = create_comment_controller(post_id, current_user["userId"], payload)
    return JSONResponse(status_code=status_code, content=body)


@router.get("")
async def list_comments(post_id: str = Path(...), current_user: dict | None = Depends(optional_authenticate)) -> dict:
    """GET /v1/posts/{post_id}/comments: List comments for a post."""
    status_code, body = get_post_comments_controller(post_id)
    return JSONResponse(status_code=status_code, content=body)


@router.delete("/{comment_id}")
async def remove_comment(post_id: str = Path(...), comment_id: str = Path(...), current_user: dict = Depends(authenticate)) -> dict:
    """DELETE /v1/posts/{post_id}/comments/{comment_id}: Delete a comment as its author."""
    status_code, body = delete_comment_controller(comment_id, current_user["userId"])
    return JSONResponse(status_code=status_code, content=body)
