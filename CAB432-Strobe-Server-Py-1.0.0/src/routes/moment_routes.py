from fastapi import APIRouter, Body, Depends
from fastapi.responses import JSONResponse

from ..controllers.moment_controller import (
    create_moment_controller,
    delete_moment_controller,
    get_moment_archive_controller,
    get_moment_feed_controller,
    hide_moment_controller,
)
from ..middleware.auth import authenticate, require_moderator

router = APIRouter()


@router.post("")
async def create(payload: dict = Body(...), current_user: dict = Depends(authenticate)) -> dict:
    """POST /v1/moments: Create a new moment for the authenticated user."""
    status_code, body = create_moment_controller(current_user["userId"], payload)
    return JSONResponse(status_code=status_code, content=body)


@router.get("/feed")
async def feed(current_user: dict = Depends(authenticate)) -> dict:
    """GET /v1/moments/feed: Return active moments for the authenticated user's network."""
    status_code, body = get_moment_feed_controller(current_user["userId"], current_user["userRole"])
    return JSONResponse(status_code=status_code, content=body)


@router.get("/archive")
async def archive(current_user: dict = Depends(authenticate)) -> dict:
    """GET /v1/moments/archive: Return archived moments available to the authenticated user."""
    status_code, body = get_moment_archive_controller(current_user["userId"], current_user["userRole"])
    return JSONResponse(status_code=status_code, content=body)


@router.post("/{moment_id}/hide")
async def hide(moment_id: str, current_user: dict = Depends(require_moderator)) -> dict:
    """POST /v1/moments/{moment_id}/hide: Moderator-only moment hide action."""
    status_code, body = hide_moment_controller(moment_id, current_user["userId"], current_user["userRole"])
    return JSONResponse(status_code=status_code, content=body)


@router.delete("/{moment_id}")
async def remove(moment_id: str, current_user: dict = Depends(authenticate)) -> dict:
    """DELETE /v1/moments/{moment_id}: Delete a moment as owner or moderator."""
    status_code, body = delete_moment_controller(moment_id, current_user["userId"], current_user["userRole"])
    return JSONResponse(status_code=status_code, content=body)
