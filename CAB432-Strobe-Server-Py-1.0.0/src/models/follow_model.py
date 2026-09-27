from __future__ import annotations
from typing import Any
from ..utils.id_generator import generate_id
from ..config.dynamo import table
from .common import now_iso
from boto3.dynamodb.conditions import Attr


def _all_follows() -> list[dict[str, Any]]:
    return table("follows").scan().get("Items", [])


def find_follow(follower_id: str, followee_id: str) -> dict[str, Any] | None:
    matches = [f for f in _all_follows() if f["followerId"] == follower_id and f["followeeId"] == followee_id]
    return matches[0] if matches else None


def is_following(follower_id: str | None, followee_id: str) -> bool:
    if not follower_id:
        return False
    return find_follow(follower_id, followee_id) is not None


def get_following(user_id: str) -> list[str]:
    return [f["followeeId"] for f in _all_follows() if f["followerId"] == user_id]


def get_followers(user_id: str) -> list[str]:
    return [f["followerId"] for f in _all_follows() if f["followeeId"] == user_id]


def get_following_count(user_id: str) -> int:
    return len(get_following(user_id))


def get_follower_count(user_id: str) -> int:
    return len(get_followers(user_id))


def create_follow(follow_data: dict[str, Any]) -> dict[str, Any]:
    follow = {
        "id": follow_data.get("id", generate_id()),
        "followerId": follow_data["followerId"],
        "followeeId": follow_data["followeeId"],
        "createdAt": follow_data.get("createdAt", now_iso()),
    }
    table("follows").put_item(Item=follow)
    return follow


def remove_follow(follower_id: str, followee_id: str) -> bool:
    existing = find_follow(follower_id, followee_id)
    if not existing:
        return False
    table("follows").delete_item(Key={"id": existing["id"]})
    return True


def remove_follows_by_user_id(user_id: str) -> None:
    for f in _all_follows():
        if f["followerId"] == user_id or f["followeeId"] == user_id:
            table("follows").delete_item(Key={"id": f["id"]})