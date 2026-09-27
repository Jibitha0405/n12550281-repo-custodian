from fastapi import APIRouter, Body, Depends, status
from fastapi.responses import JSONResponse

from ..controllers.upload_controller import get_upload_url_controller
from ..middleware.auth import authenticate

router = APIRouter()


@router.post("/url")
async def upload_url(payload: dict = Body(...), current_user: dict = Depends(authenticate)) -> dict:
    """POST /v1/uploads/url: Create one-time upload URL data for an authenticated user."""
    status_code, body = get_upload_url_controller(current_user["userId"], payload)
    return JSONResponse(status_code=status_code, content=body)