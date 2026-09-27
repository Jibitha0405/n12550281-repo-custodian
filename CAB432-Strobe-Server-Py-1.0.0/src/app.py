from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException, RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config.settings import settings
from .middleware.error_handler import error_handler, http_exception_handler, validation_error_handler
from .routes.auth_routes import router as auth_router
from .routes.comment_routes import router as comment_router
from .routes.feed_routes import router as feed_router
from .routes.follow_routes import router as follow_router
from .routes.moment_routes import router as moment_router
from .routes.post_routes import router as post_router
from .routes.upload_routes import router as upload_router
from .routes.user_routes import router as user_router

app = FastAPI(title="Strobe Python Server", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict[str, str]:
    """Return a lightweight health response for service monitoring."""
    return {"status": "ok", "timestamp": settings.now_iso()}


app.include_router(auth_router, prefix="/v1/auth")
app.include_router(post_router, prefix="/v1/posts")
app.include_router(feed_router, prefix="/v1/feed")
app.include_router(user_router, prefix="/v1/users")
app.include_router(comment_router, prefix="/v1/posts/{post_id}/comments")
app.include_router(follow_router, prefix="/v1/users/{user_id}")
app.include_router(upload_router, prefix="/v1/uploads")
app.include_router(moment_router, prefix="/v1/moments")


@app.exception_handler(HTTPException)
async def fastapi_http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Normalize FastAPI HTTP exceptions into API error payloads."""
    return await http_exception_handler(request, exc)


@app.exception_handler(RequestValidationError)
async def fastapi_validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Normalize FastAPI validation errors into API error payloads."""
    return await validation_error_handler(request, exc)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected exceptions with a safe generic API response."""
    return await error_handler(request, exc)