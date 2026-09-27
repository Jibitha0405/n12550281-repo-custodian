from __future__ import annotations
from typing import Any
from ..utils.id_generator import generate_id
from ..config.dynamo import table
from .common import now_iso


def find_post_by_id(post_id: str) -> dict[str, Any] | None:
    return table("posts").get_item(Key={"id": post_id}).get("Item")


def _all_posts() -> list[dict[str, Any]]:
    return table("posts").scan().get("Items", [])


def get_posts_by_user_id(user_id: str, limit: int = 20, offset: int = 0) -> list[dict[str, Any]]:
    posts = [p for p in _all_posts() if p["userId"] == user_id]
    posts.sort(key=lambda p: p["createdAt"], reverse=True)
    return posts[offset:offset + limit]


def get_all_posts(limit: int = 20, offset: int = 0) -> list[dict[str, Any]]:
    posts = _all_posts()
    posts.sort(key=lambda p: p["createdAt"], reverse=True)
    return posts[offset:offset + limit]


def create_post(post_data: dict[str, Any]) -> dict[str, Any]:
    post = {
        "id": post_data.get("id", generate_id()),
        "userId": post_data["userId"],
        "title": post_data["title"],
        "description": post_data.get("description", ""),
        "images": list(post_data.get("images", [])),
        "status": post_data.get("status", "active"),
        "hiddenBy": post_data.get("hiddenBy"),
        "hiddenAt": post_data.get("hiddenAt"),
        "createdAt": post_data.get("createdAt", now_iso()),
        "updatedAt": post_data.get("updatedAt", now_iso()),
    }
    table("posts").put_item(Item=post)
    return post


def update_post(post_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
    post = table("posts").get_item(Key={"id": post_id}).get("Item")
    if not post:
        return None
    for key, value in updates.items():
        if value is not None and key != "id":
            post[key] = value
    post["updatedAt"] = now_iso()
    table("posts").put_item(Item=post)
    return post


def delete_post(post_id: str) -> bool:
    if not table("posts").get_item(Key={"id": post_id}).get("Item"):
        return False
    table("posts").delete_item(Key={"id": post_id})
    return True


def get_posts_from_users(user_ids: list[str], limit: int = 20, offset: int = 0) -> list[dict[str, Any]]:
    posts = [p for p in _all_posts() if p["userId"] in user_ids]
    posts.sort(key=lambda p: p["createdAt"], reverse=True)
    return posts[offset:offset + limit]


def get_post_count_by_user_id(user_id: str) -> int:
    return sum(1 for p in _all_posts() if p["userId"] == user_id)


def delete_posts_by_user_id(user_id: str) -> None:
    for p in _all_posts():
        if p["userId"] == user_id:
            table("posts").delete_item(Key={"id": p["id"]})