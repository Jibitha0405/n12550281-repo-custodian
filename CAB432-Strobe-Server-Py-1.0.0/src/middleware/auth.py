from __future__ import annotations
from fastapi import Depends, HTTPException, Request, status
from ..errors import AppError, forbidden_error, unauthorised_error
from ..models.user_model import find_user_by_id
from ..config.constants import ROLE_MODERATOR


async def authenticate(request: Request) -> dict:
    event = request.scope.get("aws.event", {})
    claims = (
        event.get("requestContext", {})
        .get("authorizer", {})
        .get("jwt", {})
        .get("claims", {})
    )
    if not claims or "sub" not in claims:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing or invalid token")

    groups_raw = claims.get("cognito:groups", "")
    role = "moderator" if "moderator" in groups_raw else "user"

    return {
        "userId": claims["sub"],
        "userRole": role,
        "username": claims.get("email", ""),
    }


async def optional_authenticate(request: Request) -> dict | None:
    try:
        return await authenticate(request)
    except HTTPException:
        return None


async def require_moderator(current_user: dict = Depends(authenticate)) -> dict:
    if current_user.get("userRole") != ROLE_MODERATOR:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Moderator access required")
    return current_user