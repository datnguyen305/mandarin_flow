from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import dictionary, subtitles, videos, vocabulary
from app.core.config import settings
from app.core.errors import AppError
from app.core.logging import configure_logging

configure_logging()

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url, "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(AppError)
async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"error": {"code": exc.code, "message": exc.message}})


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(videos.router, prefix="/api")
app.include_router(subtitles.router, prefix="/api")
app.include_router(dictionary.router, prefix="/api")
app.include_router(vocabulary.router, prefix="/api")
