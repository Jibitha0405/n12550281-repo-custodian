from __future__ import annotations
from typing import Any
from ..utils.id_generator import generate_id
from ..config.dynamo import table
from .common import now_iso
from boto3.dynamodb.conditions import Attr


def _likes_for_post(post_id: str) -> list[dict[str, Any]]:
    resp = table("likes").scan(FilterExpression=Attr("postId").eq(post_id))
    return resp.get("Items", [])


def find_like(post_id: str, user_id: str) -> dict[str, Any] | None:
    matches = [l for l in _likes_for_post(post_id) if l["userId"] == user_id]
    return matches[0] if matches else None


def has_user_liked_post(post_id: str, user_id: str | None) -> bool:
    if not user_id:
        return False
    return find_like(post_id, user_id) is not None


def get_like_count_by_post_id(post_id: str) -> int:
    return len(_likes_for_post(post_id))


def create_like(like_data: dict[str, Any]) -> dict[str, Any]:
    like = {
        "id": like_data.get("id", generate_id()),
        "postId": like_data["postId"],
        "userId": like_data["userId"],
        "createdAt": like_data.get("createdAt", now_iso()),
    }
    table("likes").put_item(Item=like)
    return like


def remove_like(post_id: str, user_id: str) -> bool:
    existing = find_like(post_id, user_id)
    if not existing:
        return False
    table("likes").delete_item(Key={"id": existing["id"]})
    return True


def remove_likes_by_post_id(post_id: str) -> None:
    for l in _likes_for_post(post_id):
        table("likes").delete_item(Key={"id": l["id"]})


def remove_likes_by_user_id(user_id: str) -> None:
    resp = table("likes").scan(FilterExpression=Attr("userId").eq(user_id))
    for l in resp.get("Items", []):
        table("likes").delete_item(Key={"id": l["id"]})