from __future__ import annotations
import os
import boto3
from botocore.client import Config
from ..errors import validation_error
from ..utils.id_generator import generate_short_id
s3 = boto3.client(
    "s3",
    region_name="ap-southeast-2",
    config=Config(signature_version="s3v4"),
)
BUCKET = os.environ.get("MEDIA_BUCKET", "n12550281-strobe-media")
def get_upload_url(user_id: str, post_id: str) -> dict:
    if not post_id:
        raise validation_error("Post ID is required")
    file_id = generate_short_id()
    key = f"{user_id}/{post_id}/{file_id}"
    url = s3.generate_presigned_url(
        "put_object",
        Params={"Bucket": BUCKET, "Key": key},
        ExpiresIn=300,
    )
    return {"uploadUrl": url, "fileId": file_id, "key": key}
def get_file_url(key: str) -> str | None:
    """Generate a short-lived GET URL for reading an uploaded image."""
    if not key:
        return None
    return s3.generate_presigned_url(
        "get_object", Params={"Bucket": BUCKET, "Key": key}, ExpiresIn=300
    )