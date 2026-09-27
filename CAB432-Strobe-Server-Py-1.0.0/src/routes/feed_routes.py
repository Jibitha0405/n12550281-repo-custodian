from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from ..controllers.feed_controller import get_personal_feed_controller
from ..middleware.auth import authenticate

router = APIRouter()


@router.get("")
async def get_feed(limit: int = Query(default=20), offset: int = Query(default=0), current_user: dict = Depends(authenticate)) -> dict:
    """GET /v1/feed: Return personalized feed posts for the authenticated user."""
    status_code, body = get_personal_feed_controller(
        current_user["userId"],
        limit,
        offset,
        current_user["userRole"],
    )
    return JSONResponse(status_code=status_code, content=body)
