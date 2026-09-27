from __future__ import annotations

import shutil
from pathlib import Path

from ..config.settings import settings
from ..config.constants import ROLE_USER
from ..errors import conflict_error, forbidden_error, not_found_error, unauthorised_error, validation_error
from ..models.user_model import (
    create_user,
    delete_user_with_cascade,
    email_exists,
    find_user_auth_by_email,
    find_user_by_id,
    get_all_users,
    search_users,
)
from ..utils.enrichment import enrich_user, enrich_users
from ..utils.validation import validate_email, validate_password, validate_role
import os
import boto3

cognito = boto3.client("cognito-idp", region_name="ap-southeast-2")
COGNITO_CLIENT_ID = os.environ["COGNITO_CLIENT_ID"]
COGNITO_POOL_ID = os.environ["COGNITO_POOL_ID"]


def register_user(user_data: dict) -> dict:
    print(f"DEBUG register_user received: email={user_data.get('email')!r}, password_len={len(user_data.get('password') or '')}, role={user_data.get('role')!r}")
    email = user_data.get("email")
    password = user_data.get("password")
    requested_role = user_data.get("role", ROLE_USER)
    username = email

    for validator in (validate_email(email), validate_password(password)):
        if not validator["valid"]:
            raise validation_error(str(validator["error"]))

    role_validation = validate_role(requested_role)
    if not role_validation["valid"]:
        raise validation_error(str(role_validation["error"]))

    if email_exists(email):
        raise conflict_error("Email already exists")

    try:
        signup_resp = cognito.sign_up(
            ClientId=COGNITO_CLIENT_ID, Username=email, Password=password,
            UserAttributes=[{"Name": "email", "Value": email}],
        )
    except cognito.exceptions.UsernameExistsException:
        raise conflict_error("Email already exists")

    cognito.admin_confirm_sign_up(UserPoolId=COGNITO_POOL_ID, Username=email)

    user = create_user({
        "id": signup_resp["UserSub"],
        "username": username,
        "email": email,
        "role": requested_role,
    })

    token_resp = cognito.admin_initiate_auth(
        UserPoolId=COGNITO_POOL_ID, ClientId=COGNITO_CLIENT_ID,
        AuthFlow="ADMIN_USER_PASSWORD_AUTH",
        AuthParameters={"USERNAME": email, "PASSWORD": password},
    )
    token = token_resp["AuthenticationResult"]["AccessToken"]
    return {"user": user, "token": token}


def login_user(credentials: dict) -> dict:
    email = credentials.get("email") or credentials.get("username")
    password = credentials.get("password")

    if not email or not password:
        raise unauthorised_error("Invalid email or password")

    try:
        token_resp = cognito.admin_initiate_auth(
            UserPoolId=COGNITO_POOL_ID, ClientId=COGNITO_CLIENT_ID,
            AuthFlow="ADMIN_USER_PASSWORD_AUTH",
            AuthParameters={"USERNAME": email, "PASSWORD": password},
        )
    except Exception:
        raise unauthorised_error("Invalid email or password")

    auth_user = find_user_auth_by_email(email)
    if not auth_user:
        raise unauthorised_error("Invalid email or password")

    user = find_user_by_id(auth_user["id"])
    token = token_resp["AuthenticationResult"]["AccessToken"]
    return {"user": user, "token": token}


def get_user_profile(user_id: str, current_user_id: str | None = None) -> dict:
    """Return one enriched user profile by ID."""
    user = find_user_by_id(user_id)
    if not user:
        raise not_found_error("User not found")
    return enrich_user(user, current_user_id)


def list_users(query: str = "", limit: int = 20, current_user_id: str | None = None) -> list[dict]:
    """Return enriched user list with optional query filtering and bounded limit."""
    limit = max(1, min(int(limit), 100))
    users = search_users(query or "", limit=limit) if query else get_all_users()[:limit]
    return enrich_users(users, current_user_id)


def delete_user_account(authenticated_user_id: str, target_user_id: str) -> None:
    """Delete an account owned by the authenticated user and remove from Cognito."""
    if authenticated_user_id != target_user_id:
        raise forbidden_error("You can only delete your own account")

    user = find_user_by_id(target_user_id)
    if not user:
        raise not_found_error("User not found")

    try:
        cognito.admin_delete_user(UserPoolId=COGNITO_POOL_ID, Username=user["email"])
    except cognito.exceptions.UserNotFoundException:
        pass

    if not delete_user_with_cascade(target_user_id):
        raise not_found_error("User not found")

