from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]


def load_env_file(file_path: Path) -> None:
    """Load simple KEY=value pairs from .env without overriding shell variables."""
    if not file_path.exists():
        return

    for line in file_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue

        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


load_env_file(ROOT_DIR / ".env")


@dataclass(frozen=True)
class Settings:
    """Store runtime configuration values for the Python server."""
    port: int = int(os.getenv("PORT", "3000"))
    host: str = os.getenv("HOST", "0.0.0.0")
    node_env: str = os.getenv("NODE_ENV", "development")
    jwt_secret: str = os.getenv("JWT_SECRET", "dev-secret-change-in-production")
    uploads_dir: str = os.getenv("UPLOADS_DIR", "uploads")
    public_base_url: str = os.getenv("PUBLIC_BASE_URL", "").strip().rstrip("/")

    def now_iso(self) -> str:
        """Return the current UTC timestamp in ISO-8601 format."""
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    @property
    def root_dir(self) -> Path:
        """Return the project root directory used to resolve runtime paths."""
        return ROOT_DIR

    def to_public_url(self, pathname: str) -> str:
        """Build an absolute URL when PUBLIC_BASE_URL is set, else keep a relative path."""
        if not pathname:
            return self.public_base_url or ""
        if not self.public_base_url:
            return pathname
        suffix = pathname if pathname.startswith("/") else f"/{pathname}"
        return f"{self.public_base_url}{suffix}"


settings = Settings()
