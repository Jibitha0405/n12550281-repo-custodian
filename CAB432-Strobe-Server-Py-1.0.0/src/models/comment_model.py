from __future__ import annotations
from typing import Any
from ..utils.id_generator import generate_id
from ..config.dynamo import table
from .common import now_iso
from boto3.dynamodb.conditions import Attr


def find_comment_by_id(comment_id: str) -> dict[str, Any] | None:
    return table("comments").get_item(Key={"id": comment_id}).get("Item")


def get_comments_by_post_id(post_id: str) -> list[dict[str, Any]]:
    resp = table("comments").scan(FilterExpression=Attr("postId").eq(post_id))
    comments = resp.get("Items", [])
    comments.sort(key=lambda c: c["createdAt"])
    return comments


def create_comment(comment_data: dict[str, Any]) -> dict[str, Any]:
    comment = {
        "id": comment_data.get("id", generate_id()),
        "postId": comment_data["postId"],
        "userId": comment_data["userId"],
        "text": comment_data["text"],
        "createdAt": comment_data.get("createdAt", now_iso()),
        "updatedAt": comment_data.get("updatedAt", now_iso()),
    }
    table("comments").put_item(Item=comment)
    return comment


def delete_comment(comment_id: str) -> bool:
    if not table("comments").get_item(Key={"id": comment_id}).get("Item"):
        return False
    table("comments").delete_item(Key={"id": comment_id})
    return True


def get_comment_count_by_post_id(post_id: str) -> int:
    resp = table("comments").scan(FilterExpression=Attr("postId").eq(post_id))
    return len(resp.get("Items", []))


def delete_comments_by_post_id(post_id: str) -> None:
    resp = table("comments").scan(FilterExpression=Attr("postId").eq(post_id))
    for c in resp.get("Items", []):
        table("comments").delete_item(Key={"id": c["id"]})