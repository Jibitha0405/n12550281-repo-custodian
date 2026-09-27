from __future__ import annotations

from datetime import datetime, timedelta, timezone
from random import randint

from faker import Faker

from ..config.constants import MOMENT_DURATION_HOURS, ROLE_MODERATOR, ROLE_USER
from ..config.database import get_database, initialise_database, save_database
from ..models.common import now_iso
from ..utils.id_generator import generate_id
from ..utils.password import hash_password


faker = Faker()


def _image_url(width: int = 1200, height: int = 900) -> str:
    # Picsum seeded URLs are stable and generally load more reliably than Faker image providers.
    """Build a deterministic seed image URL for fixtures."""
    return f"https://picsum.photos/seed/{generate_id()}/{width}/{height}"


def _random_past_iso() -> str:
    """Generate a random ISO timestamp in the past."""
    return faker.date_time_between(start_date="-2y", end_date="now", tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")


def _random_recent_iso(days: int = 2) -> str:
    """Generate a random ISO timestamp from recent days."""
    start = datetime.now(timezone.utc) - timedelta(days=days)
    return faker.date_time_between(start_date=start, end_date="now", tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")


def _pick_many(items: list[dict], count: int) -> list[dict]:
    """Select multiple unique random items from a list."""
    return faker.random_elements(elements=items, length=min(count, len(items)), unique=True)


def _create_record_with_timestamps(record: dict) -> dict:
    """Attach created and updated timestamps to a record."""
    return {**record, "createdAt": _random_past_iso(), "updatedAt": now_iso()}


def _generate_users(count: int = 10) -> list[dict]:
    """Generate seed users with default credentials and roles."""
    users = []
    for index in range(count):
        email = faker.email()
        users.append(
            {
                "id": generate_id(),
                "username": email,
                "email": email,
                "password": hash_password("password123"),
                "role": ROLE_MODERATOR if index == 0 else ROLE_USER,
                "createdAt": _random_past_iso(),
                "updatedAt": now_iso(),
            }
        )
    return users


def _generate_posts(users: list[dict], posts_per_user: int = 3) -> list[dict]:
    """Generate seed posts for each user."""
    posts: list[dict] = []
    for user in users:
        for _ in range(posts_per_user):
            images = [_image_url(1200, 900), _image_url(1200, 900)][: randint(0, 2)]
            posts.append(
                _create_record_with_timestamps(
                    {
                        "id": generate_id(),
                        "userId": user["id"],
                        "title": faker.sentence(),
                        "description": faker.paragraph(nb_sentences=1),
                        "images": images,
                        "status": "active",
                        "hiddenBy": None,
                        "hiddenAt": None,
                    }
                )
            )
    return posts


def _generate_follows(users: list[dict]) -> list[dict]:
    """Generate seed follow relationships between users."""
    follows: list[dict] = []
    for user in users:
        follow_count = randint(2, 5)
        for followee in _pick_many(users, follow_count):
            if user["id"] != followee["id"]:
                follows.append(
                    {
                        "id": generate_id(),
                        "followerId": user["id"],
                        "followeeId": followee["id"],
                        "createdAt": _random_past_iso(),
                    }
                )
    return follows


def _generate_likes(posts: list[dict], users: list[dict]) -> list[dict]:
    """Generate seed likes for generated posts."""
    likes: list[dict] = []
    for post in posts:
        liker_count = randint(0, 5)
        for liker in _pick_many(users, liker_count):
            if liker["id"] != post["userId"]:
                likes.append(
                    {
                        "id": generate_id(),
                        "postId": post["id"],
                        "userId": liker["id"],
                        "createdAt": _random_past_iso(),
                    }
                )
    return likes


def _generate_comments(posts: list[dict], users: list[dict]) -> list[dict]:
    """Generate seed comments for generated posts."""
    comments: list[dict] = []
    for post in posts:
        for _ in range(randint(0, 5)):
            author = faker.random_element(elements=users)
            comments.append(
                _create_record_with_timestamps(
                    {
                        "id": generate_id(),
                        "postId": post["id"],
                        "userId": author["id"],
                        "text": faker.sentence(),
                    }
                )
            )
    return comments


def _generate_moments(users: list[dict]) -> list[dict]:
    """Generate seed moments for generated users."""
    moments: list[dict] = []
    for user in users:
        for _ in range(randint(1, 3)):
            created_at = _random_recent_iso(2)
            created_dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            expires_dt = created_dt + timedelta(hours=MOMENT_DURATION_HOURS)
            moments.append(
                {
                    "id": generate_id(),
                    "userId": user["id"],
                    "imageUrl": _image_url(1080, 1920),
                    "caption": faker.sentence(),
                    "status": "archived" if expires_dt < datetime.now(timezone.utc) else "active",
                    "hiddenBy": None,
                    "hiddenAt": None,
                    "archivedAt": None,
                    "createdAt": created_at,
                    "expiresAt": expires_dt.isoformat().replace("+00:00", "Z"),
                    "updatedAt": now_iso(),
                }
            )
    return moments


def seed() -> None:
    """Populate the JSON database with deterministic demo data."""
    print("Seeding database...\n")

    initialise_database()
    db = get_database()

    for key in ["users", "posts", "follows", "likes", "comments", "moments"]:
        db[key] = []

    print("Generating users...")
    users = _generate_users(10)
    db["users"] = users
    print(f"  {len(users)} users created")

    print("Generating posts...")
    posts = _generate_posts(users, 3)
    db["posts"] = posts
    print(f"  {len(posts)} posts created")

    print("Generating follows...")
    follows = _generate_follows(users)
    db["follows"] = follows
    print(f"  {len(follows)} follow relationships created")

    print("Generating likes...")
    likes = _generate_likes(posts, users)
    db["likes"] = likes
    print(f"  {len(likes)} likes created")

    print("Generating comments...")
    comments = _generate_comments(posts, users)
    db["comments"] = comments
    print(f"  {len(comments)} comments created")

    print("Generating moments...")
    moments = _generate_moments(users)
    db["moments"] = moments
    print(f"  {len(moments)} moments created")

    save_database()

    print("\nDatabase seeded successfully.\n")
    print("Sample credentials:")
    for index, user in enumerate(users[:3], start=1):
        print(f"   {index}. Email: {user['email']}, Password: password123, Role: {user['role']}")

    print("\n")


if __name__ == "__main__":
    seed()
