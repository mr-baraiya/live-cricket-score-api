import logging
from typing import Optional
from fastapi import FastAPI, Request, Path
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import JSONResponse, HTMLResponse
from pydantic import BaseModel, field_validator
from starlette.exceptions import HTTPException as StarletteHTTPException

from models import (
    LiveMatchesResponse,
    UpcomingMatchesResponse,
    MatchOverviewResponse,
    ScorecardResponse,
    CommentaryResponse,
    RecentEventResponse,
    FullMatchResponse,
    HealthStatusResponse,
    ChangeDetectionResult,
)
from services import match_service

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("cricbuzz.api")


class APIError(Exception):
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message


class MatchValidator(BaseModel):
    score: str

    @field_validator("score")
    @classmethod
    def validate_match_id(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("invalid match id")
        if not value.isdigit():
            raise ValueError("match id must contain digits only")
        if len(value) < 4:
            raise ValueError("match id must be at least 4 digits")
        if len(value) > 20:
            raise ValueError("match id too long")
        return value


class RootAPIInfoResponse(BaseModel):
    name: str = "Live Cricket Score & Commentary API"
    version: str = "0.0.1"
    status: str = "online"


app = FastAPI(
    title="Live Cricket Score & Commentary API",
    version="0.0.1",
    description="Clean, modular JSON API for live Cricbuzz scores & commentary",
    docs_url=None,
    redoc_url=None
)

import os

cors_origins_env = os.getenv("CORS_ORIGINS", "*")
allowed_origins = [o.strip() for o in cors_origins_env.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


@app.get("/docs", include_in_schema=False)
async def custom_swagger_docs():
    try:
        html_doc = get_swagger_ui_html(
            openapi_url=app.openapi_url,
            title="Live Cricket Score & Commentary API Docs",
            swagger_favicon_url="https://fastapi.tiangolo.com/img/favicon.png"
        )
        content = html_doc.body.decode("utf-8")
        custom_style = """
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1">
        <style>
            html, body { margin: 0; padding: 0; width: 100%; overflow-x: hidden; }
            .swagger-ui { width: 100%; overflow-x: hidden; }
            .swagger-ui .wrapper { width: 100%; max-width: 100% !important; padding: 10px !important; box-sizing: border-box; }
        </style>
        """
        content = content.replace("</head>", custom_style + "</head>")
        response = HTMLResponse(content=content)
        response.headers["Cache-Control"] = "no-store"
        return response
    except Exception:
        return HTMLResponse(content="<h2>Unable to load Swagger docs</h2>", status_code=500)


@app.get("/", response_model=RootAPIInfoResponse)
async def root():
    return RootAPIInfoResponse()


@app.get("/health", response_model=HealthStatusResponse)
async def health_check():
    return match_service.get_health()


@app.get("/matches/live", response_model=LiveMatchesResponse)
async def get_live_matches():
    return await match_service.get_live_matches()


@app.get("/matches/upcoming", response_model=UpcomingMatchesResponse)
async def get_upcoming_matches():
    return await match_service.get_upcoming_matches()


@app.get("/match/{id}", response_model=MatchOverviewResponse)
async def get_match_overview(id: str = Path(..., min_length=4, max_length=20)):
    MatchValidator(score=id)
    return await match_service.get_match_overview(id)


@app.get("/match/{id}/scorecard", response_model=ScorecardResponse)
async def get_match_scorecard(id: str = Path(..., min_length=4, max_length=20)):
    MatchValidator(score=id)
    return await match_service.get_scorecard(id)


@app.get("/match/{id}/commentary", response_model=CommentaryResponse)
async def get_match_commentary(id: str = Path(..., min_length=4, max_length=20)):
    MatchValidator(score=id)
    return await match_service.get_commentary(id)


@app.get("/match/{id}/recent", response_model=RecentEventResponse)
async def get_match_recent(id: str = Path(..., min_length=4, max_length=20)):
    MatchValidator(score=id)
    return await match_service.get_recent_event(id)


@app.get("/match/{id}/full", response_model=FullMatchResponse)
async def get_match_full(id: str = Path(..., min_length=4, max_length=20)):
    MatchValidator(score=id)
    return await match_service.get_full_match(id)


@app.get("/match/{id}/changes", response_model=ChangeDetectionResult)
async def get_match_changes(id: str = Path(..., min_length=4, max_length=20)):
    MatchValidator(score=id)
    return await match_service.detect_match_changes(id)


@app.exception_handler(APIError)
async def api_error_handler(request: Request, exc: APIError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"status": "error", "code": exc.status_code, "message": exc.message}
    )


@app.exception_handler(StarletteHTTPException)
async def http_error_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"status": "error", "code": exc.status_code, "message": "invalid api route"}
    )


@app.exception_handler(Exception)
async def global_error_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception in API route: %s", exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"status": "error", "code": 500, "message": "internal server error"}
    )