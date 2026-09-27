from __future__ import annotations
from typing import Any
from ..utils.id_generator import generate_id
from ..config.dynamo import table
from .common import now_iso
from boto3.dynamodb.conditions import Attr


def create_moment(moment_data: dict[str, Any]) -> dict[str, Any]:
    moment = {
        "id": moment_data.get("id", generate_id()),
        "userId": moment_data["userId"],
        "imageUrl": moment_data["imageUrl"],
        "caption": moment_data.get("caption", ""),
        "status": moment_data.get("status", "active"),
        "hiddenBy": moment_data.get("hiddenBy"),
        "hiddenAt": moment_data.get("hiddenAt"),
        "archivedAt": moment_data.get("archivedAt"),
        "createdAt": moment_data.get("createdAt", now_iso()),
        "expiresAt": moment_data.get("expiresAt"),
        "updatedAt": moment_data.get("updatedAt", now_iso()),
    }
    table("moments").put_item(Item=moment)
    return moment


def find_moment_by_id(moment_id: str) -> dict[str, Any] | None:
    return table("moments").get_item(Key={"id": moment_id}).get("Item")


def update_moment(moment_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
    moment = table("moments").get_item(Key={"id": moment_id}).get("Item")
    if not moment:
        return None
    for key, value in updates.items():
        if value is not None and key != "id":
            moment[key] = value
    moment["updatedAt"] = now_iso()
    table("moments").put_item(Item=moment)
    return moment


def delete_moment(moment_id: str) -> bool:
    if not table("moments").get_item(Key={"id": moment_id}).get("Item"):
        return False
    table("moments").delete_item(Key={"id": moment_id})
    return True


def get_moments_by_user_ids(user_ids: list[str]) -> list[dict[str, Any]]:
    resp = table("moments").scan()
    moments = [m for m in resp.get("Items", []) if m["userId"] in user_ids]
    moments.sort(key=lambda m: m["createdAt"], reverse=True)
    return moments


def get_moments_by_user_id(user_id: str) -> list[dict[str, Any]]:
    return get_moments_by_user_ids([user_id])


def delete_moments_by_user_id(user_id: str) -> None:
    resp = table("moments").scan(FilterExpression=Attr("userId").eq(user_id))
    for m in resp.get("Items", []):
        table("moments").delete_item(Key={"id": m["id"]})