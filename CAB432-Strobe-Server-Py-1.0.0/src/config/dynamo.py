import boto3
import os

_dynamodb = boto3.resource("dynamodb", region_name="ap-southeast-2")

TABLE_NAMES = {
    "users": os.environ.get("USERS_TABLE", "n12550281-ddb-users"),
    "posts": os.environ.get("POSTS_TABLE", "n12550281-ddb-post"),
    "comments": os.environ.get("COMMENTS_TABLE", "n12550281-ddb-comments"),
    "likes": os.environ.get("LIKES_TABLE", "n12550281-ddb-likes"),
    "follows": os.environ.get("FOLLOWS_TABLE", "n12550281-ddb-follows"),
    "moments": os.environ.get("MOMENTS_TABLE", "n12550281-ddb-moments"),
}

def table(name):
    return _dynamodb.Table(TABLE_NAMES[name])