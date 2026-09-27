import uvicorn

from .app import app
from .config.settings import settings


if __name__ == "__main__":
    uvicorn.run("src.app:app", host=settings.host, port=settings.port, reload=False)
