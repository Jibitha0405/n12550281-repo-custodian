from __future__ import annotations
from typing import Any
from boto3.dynamodb.conditions import Attr
from ..utils.id_generator import generate_id
from ..config.dynamo import table
from .common import now_iso


def sanitize_user(user: dict[str, Any] | None) -> dict[str, Any] | None:
    if user is None:
        return None
    sanitized = dict(user)
    sanitized.pop("password", None)
    return sanitized


def find_user_by_id(user_id: str) -> dict[str, Any] | None:
    resp = table("users").get_item(Key={"id": user_id})
    return sanitize_user(resp.get("Item"))


def find_user_auth_by_email(email: str) -> dict[str, Any] | None:
    resp = table("users").scan(FilterExpression=Attr("email").eq(email))
    items = resp.get("Items", [])
    return items[0] if items else None


def get_all_users() -> list[dict[str, Any]]:
    resp = table("users").scan()
    return [sanitize_user(u) for u in resp.get("Items", [])]


def create_user(user_data: dict[str, Any]) -> dict[str, Any]:
    user = {
        "id": user_data.get("id", generate_id()),
        "username": user_data["username"],
        "email": user_data["email"],
        "password": user_data.get("password", ""),
        "role": user_data.get("role", "user"),
        "createdAt": user_data.get("createdAt", now_iso()),
        "updatedAt": user_data.get("updatedAt", now_iso()),
    }
    table("users").put_item(Item=user)
    return sanitize_user(user)


def update_user(user_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
    resp = table("users").get_item(Key={"id": user_id})
    user = resp.get("Item")
    if not user:
        return None
    user.update({k: v for k, v in updates.items() if v is not None})
    user["updatedAt"] = now_iso()
    table("users").put_item(Item=user)
    return sanitize_user(user)


def delete_user(user_id: str) -> bool:
    resp = table("users").get_item(Key={"id": user_id})
    if not resp.get("Item"):
        return False
    table("users").delete_item(Key={"id": user_id})
    return True


def username_exists(username: str) -> bool:
    resp = table("users").scan(FilterExpression=Attr("username").eq(username))
    return len(resp.get("Items", [])) > 0


def email_exists(email: str) -> bool:
    return find_user_auth_by_email(email) is not None


def search_users(query: str, limit: int = 10) -> list[dict[str, Any]]:
    if not query:
        return get_all_users()[:limit]
    resp = table("users").scan(FilterExpression=Attr("username").contains(query))
    return [sanitize_user(u) for u in resp.get("Items", [])[:limit]]


def delete_user_with_cascade(user_id: str) -> bool:
    if not table("users").get_item(Key={"id": user_id}).get("Item"):
        return False

    from .comment_model import delete_comments_by_post_id
    from .follow_model import remove_follows_by_user_id
    from .like_model import remove_likes_by_user_id
    from .moment_model import delete_moments_by_user_id
    from .post_model import delete_posts_by_user_id, get_posts_by_user_id

    posts = get_posts_by_user_id(user_id, limit=10_000, offset=0)
    delete_posts_by_user_id(user_id)
    remove_likes_by_user_id(user_id)
    remove_follows_by_user_id(user_id)
    delete_moments_by_user_id(user_id)
    for post in posts:
        delete_comments_by_post_id(post["id"])

    table("users").delete_item(Key={"id": user_id})
    return True