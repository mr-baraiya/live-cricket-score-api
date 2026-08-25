import os
import logging
from typing import Optional
from datetime import datetime, timezone
from contextlib import asynccontextmanager
import httpx
from fastapi import FastAPI, Request, Path, Body, WebSocket, WebSocketDisconnect, UploadFile, File, Form
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
from services.websocket_manager import websocket_manager
from services.live_updater import live_updater
from services import player_image_service
from services import stadium_image_service
from services import team_logo_service

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("cricket.api")


class APIError(Exception):
    def __init__(self, status_code: int, code: str, message: str):
        self.status_code = status_code
        self.code = code
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Start background live score updater
    logger.info("Initializing application lifespan & starting live updater...")
    await live_updater.start()
    yield
    # Shutdown: Stop background live score updater
    logger.info("Shutting down application lifespan & stopping live updater...")
    await live_updater.stop()


app_description = """
Clean, modular JSON & WebSocket API for live cricket scores, scorecards, commentary, and automatic updates.

### WebSocket Connection Contract:
To subscribe to automatic real-time updates for a live match:
```javascript
const socket = new WebSocket(`wss://${window.location.host}/ws/match/${matchId}`);

socket.onmessage = (event) => {
    const message = JSON.parse(event.data);
    if (message.type === "match_snapshot" || message.type === "match_update") {
        updateMatchUI(message.data);
    } else if (message.type === "match_end") {
        console.log("Match concluded:", message.match_id);
    }
};
```
"""

app = FastAPI(
    title="Live Cricket Score & Commentary API",
    version="0.0.1",
    description=app_description,
    docs_url=None,
    redoc_url=None,
    lifespan=lifespan
)

from fastapi.staticfiles import StaticFiles

cors_origins_env = os.getenv("CORS_ORIGINS", "*")
allowed_origins = [o.strip() for o in cors_origins_env.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

static_dir = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.middleware("http")
async def security_headers(request: Request, call_next):
    if request.scope.get("type") != "http" or request.url.path.startswith("/ws"):
        return await call_next(request)
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
    try:
        return await match_service.get_live_matches()
    except (httpx.TimeoutException, httpx.NetworkError):
        raise APIError(503, "SCRAPER_UNAVAILABLE", "Upstream data source temporarily unavailable")
    except Exception as exc:
        logger.error("Error in /matches/live: %s", exc)
        raise APIError(502, "UPSTREAM_ERROR", "Failed to fetch live matches")


@app.get("/matches/upcoming", response_model=UpcomingMatchesResponse)
async def get_upcoming_matches():
    try:
        return await match_service.get_upcoming_matches()
    except (httpx.TimeoutException, httpx.NetworkError):
        raise APIError(503, "SCRAPER_UNAVAILABLE", "Upstream data source temporarily unavailable")
    except Exception as exc:
        logger.error("Error in /matches/upcoming: %s", exc)
        raise APIError(502, "UPSTREAM_ERROR", "Failed to fetch upcoming matches")


def _validate_id(match_id: str):
    try:
        MatchValidator(score=match_id)
    except ValueError as val_err:
        raise APIError(422, "INVALID_MATCH_ID", str(val_err))


@app.get("/match/{id}", response_model=MatchOverviewResponse)
async def get_match_overview(id: str = Path(..., min_length=4, max_length=20)):
    _validate_id(id)
    try:
        return await match_service.get_match_overview(id)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            raise APIError(404, "MATCH_NOT_FOUND", "Match not found")
        raise APIError(502, "UPSTREAM_ERROR", "Upstream data fetch failed")
    except (httpx.TimeoutException, httpx.NetworkError):
        raise APIError(503, "SCRAPER_UNAVAILABLE", "Upstream data source temporarily unavailable")


@app.get("/match/{id}/state", response_model=FullMatchResponse)
async def get_match_state(id: str = Path(..., min_length=4, max_length=20)):
    _validate_id(id)
    try:
        return await match_service.get_cached_match_state(id)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            raise APIError(404, "MATCH_NOT_FOUND", "Match not found")
        raise APIError(502, "UPSTREAM_ERROR", "Upstream data fetch failed")
    except (httpx.TimeoutException, httpx.NetworkError):
        raise APIError(503, "SCRAPER_UNAVAILABLE", "Upstream data source temporarily unavailable")


@app.get("/match/{id}/scorecard", response_model=ScorecardResponse)
async def get_match_scorecard(id: str = Path(..., min_length=4, max_length=20)):
    _validate_id(id)
    try:
        return await match_service.get_scorecard(id)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            raise APIError(404, "MATCH_NOT_FOUND", "Match not found")
        raise APIError(502, "UPSTREAM_ERROR", "Upstream data fetch failed")
    except (httpx.TimeoutException, httpx.NetworkError):
        raise APIError(503, "SCRAPER_UNAVAILABLE", "Upstream data source temporarily unavailable")


@app.get("/match/{id}/commentary", response_model=CommentaryResponse)
async def get_match_commentary(id: str = Path(..., min_length=4, max_length=20)):
    _validate_id(id)
    try:
        return await match_service.get_commentary(id)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            raise APIError(404, "MATCH_NOT_FOUND", "Match not found")
        raise APIError(502, "UPSTREAM_ERROR", "Upstream data fetch failed")
    except (httpx.TimeoutException, httpx.NetworkError):
        raise APIError(503, "SCRAPER_UNAVAILABLE", "Upstream data source temporarily unavailable")


@app.get("/match/{id}/recent", response_model=RecentEventResponse)
async def get_match_recent(id: str = Path(..., min_length=4, max_length=20)):
    _validate_id(id)
    try:
        return await match_service.get_recent_event(id)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            raise APIError(404, "MATCH_NOT_FOUND", "Match not found")
        raise APIError(502, "UPSTREAM_ERROR", "Upstream data fetch failed")
    except (httpx.TimeoutException, httpx.NetworkError):
        raise APIError(503, "SCRAPER_UNAVAILABLE", "Upstream data source temporarily unavailable")


@app.get("/match/{id}/full", response_model=FullMatchResponse)
async def get_match_full(id: str = Path(..., min_length=4, max_length=20)):
    _validate_id(id)
    try:
        return await match_service.get_full_match(id)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            raise APIError(404, "MATCH_NOT_FOUND", "Match not found")
        raise APIError(502, "UPSTREAM_ERROR", "Upstream data fetch failed")
    except (httpx.TimeoutException, httpx.NetworkError):
        raise APIError(503, "SCRAPER_UNAVAILABLE", "Upstream data source temporarily unavailable")


@app.get("/match/{id}/changes", response_model=ChangeDetectionResult)
async def get_match_changes(id: str = Path(..., min_length=4, max_length=20)):
    _validate_id(id)
    try:
        return await match_service.detect_match_changes(id)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            raise APIError(404, "MATCH_NOT_FOUND", "Match not found")
        raise APIError(502, "UPSTREAM_ERROR", "Upstream data fetch failed")
    except (httpx.TimeoutException, httpx.NetworkError):
        raise APIError(503, "SCRAPER_UNAVAILABLE", "Upstream data source temporarily unavailable")


_match_control_store = {}


@app.get("/match/{id}/control")
async def get_match_control(id: str = Path(..., min_length=4, max_length=20)):
    _validate_id(id)
    ctrl = _match_control_store.get(id, {
        "showScoreboard": True,
        "showPlayers": True,
        "showRecentBalls": True,
        "showCommentary": True,
        "showVenue": True,
        "layout": "DEFAULT"
    })
    logger.info("[CTRL GET] match_id=%s control=%s", id, ctrl)
    return {
        "status": "success",
        "match_id": id,
        "control": ctrl
    }


@app.post("/match/{id}/control")
async def update_match_control(id: str = Path(..., min_length=4, max_length=20), control_data: dict = Body(...)):
    _validate_id(id)
    _match_control_store[id] = control_data
    client_count = websocket_manager.get_active_client_count(id)
    logger.info("[CTRL POST] match_id=%s data=%s broadcasting to %d active WS clients", id, control_data, client_count)
    await websocket_manager.broadcast_to_match(id, {
        "type": "broadcast_state",
        "match_id": id,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "data": control_data
    })
    return {"status": "success", "match_id": id, "control": control_data}


@app.websocket("/ws/match/{id}")
async def match_websocket(websocket: WebSocket, id: str):
    try:
        MatchValidator(score=id)
    except Exception:
        await websocket.close(code=4000, reason="Invalid match ID")
        return

    await websocket_manager.connect(id, websocket)
    logger.info("[WS CONNECT] match_id=%s total_clients=%d", id, websocket_manager.get_active_client_count(id))

    # Deliver current cached snapshot if available (non-blocking for WS connection)
    try:
        snapshot = await match_service.get_cached_match_state(id)
        current_ctrl = _match_control_store.get(id, {
            "showScoreboard": True,
            "showPlayers": True,
            "showRecentBalls": True,
            "showCommentary": True,
            "showVenue": True,
            "layout": "DEFAULT"
        })
        logger.info("[WS SNAPSHOT] Sending initial snapshot & control to new WS client for match %s: ctrl=%s", id, current_ctrl)
        await websocket.send_json({
            "type": "match_snapshot",
            "match_id": id,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "data": snapshot.model_dump(),
            "control": current_ctrl
        })
    except Exception as snap_err:
        logger.warning("Could not send initial snapshot for match %s: %s", id, snap_err)
        try:
            await websocket.send_json({
                "type": "broadcast_state",
                "match_id": id,
                "data": _match_control_store.get(id, {})
            })
        except Exception:
            pass

    try:
        while True:
            text = await websocket.receive_text()
            if text:
                try:
                    payload = json.loads(text)
                    logger.info("[WS RECV] match_id=%s payload_type=%s", id, payload.get("type"))
                    if payload.get("type") == "broadcast_state":
                        c_data = payload.get("data", {})
                        _match_control_store[id] = c_data
                        client_count = websocket_manager.get_active_client_count(id)
                        logger.info("[WS BROADCAST] match_id=%s data=%s clients=%d", id, c_data, client_count)
                        await websocket_manager.broadcast_to_match(id, {
                            "type": "broadcast_state",
                            "match_id": id,
                            "updated_at": datetime.now(timezone.utc).isoformat(),
                            "data": c_data
                        })
                except Exception as parse_err:
                    logger.warning("[WS PARSE ERR] match_id=%s err=%s", id, parse_err)
    except WebSocketDisconnect:
        await websocket_manager.disconnect(id, websocket)
        logger.info("[WS DISCONNECT] match_id=%s remaining=%d", id, websocket_manager.get_active_client_count(id))
    except Exception as exc:
        logger.warning("WebSocket connection exception for match %s: %s", id, exc)
        await websocket_manager.disconnect(id, websocket)


@app.get("/player/image/{player_name}")
async def get_player_image(player_name: str):
    blob_url = player_image_service.get_or_fetch_player_blob_url(player_name)
    return {"status": "success", "player_name": player_name, "blob_url": blob_url}


@app.get("/players/registry")
async def get_players_registry():
    registry = player_image_service.load_registry()
    return {"status": "success", "registry": registry}


@app.post("/player/upload")
async def upload_player_photo(
    player_name: str = Form(...),
    role_key: Optional[str] = Form(None),
    file: UploadFile = File(...)
):
    try:
        contents = await file.read()
        blob_url = player_image_service.upload_custom_player_photo(player_name, contents, role_key=role_key)
        from services.cache import match_cache
        match_cache.clear()
        
        # Broadcast update to connected match clients
        for mid in list(websocket_manager._active_connections.keys()):
            try:
                full_match = await match_service.get_full_match(mid)
                await websocket_manager.broadcast_to_match(mid, {
                    "type": "media_update",
                    "match_id": mid,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                    "data": full_match.model_dump()
                })
            except Exception as e:
                logger.warning("Error broadcasting media_update for match %s: %s", mid, e)

        return {
            "status": "success",
            "player_name": player_name,
            "blob_url": blob_url
        }
    except Exception as exc:
        raise APIError(400, "UPLOAD_FAILED", str(exc))


@app.get("/stadium/background")
async def get_stadium_background():
    data = stadium_image_service.get_stadium_background()
    return {"status": "success", "stadium": data}


@app.post("/stadium/upload")
async def upload_stadium_photo(
    file: UploadFile = File(...),
    overlay_opacity: float = Form(0.55),
    blur: int = Form(4)
):
    try:
        contents = await file.read()
        blob_url = stadium_image_service.upload_stadium_photo(contents, overlay_opacity, blur)
        stadium_info = stadium_image_service.get_stadium_background()
        
        # Broadcast stadium update to all active live match clients
        for mid in list(websocket_manager._active_connections.keys()):
            try:
                await websocket_manager.broadcast_to_match(mid, {
                    "type": "stadium_background_updated",
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                    "stadium": stadium_info
                })
            except Exception as b_err:
                logger.warning("Error broadcasting stadium update for %s: %s", mid, b_err)
        
        return {
            "status": "success",
            "blob_url": blob_url,
            "stadium": stadium_info
        }
    except Exception as exc:
        raise APIError(400, "STADIUM_UPLOAD_FAILED", str(exc))


@app.post("/team/logo/upload")
async def upload_team_logo(
    team_name: str = Form(...),
    file: UploadFile = File(...)
):
    try:
        contents = await file.read()
        blob_url = team_logo_service.upload_team_logo(team_name, contents)
        from services.cache import match_cache
        match_cache.clear()

        # Broadcast update to connected match clients
        for mid in list(websocket_manager._active_connections.keys()):
            try:
                full_match = await match_service.get_full_match(mid)
                await websocket_manager.broadcast_to_match(mid, {
                    "type": "media_update",
                    "match_id": mid,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                    "data": full_match.model_dump()
                })
            except Exception as e:
                logger.warning("Error broadcasting media_update for match %s: %s", mid, e)

        return {
            "status": "success",
            "team_name": team_name,
            "blob_url": blob_url
        }
    except Exception as exc:
        raise APIError(400, "UPLOAD_FAILED", str(exc))


@app.get("/team/logos/registry")
async def get_team_logos_registry():
    registry = team_logo_service.load_logo_registry()
    return {"status": "success", "registry": registry}


@app.get("/team/logo/{team_name}")
async def get_team_logo(team_name: str):
    blob_url = team_logo_service.get_team_logo_url(team_name)
    return {"status": "success", "team_name": team_name, "blob_url": blob_url}


@app.exception_handler(APIError)
async def api_error_handler(request: Request, exc: APIError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"status": "error", "error": {"code": exc.code, "message": exc.message}}
    )


@app.exception_handler(StarletteHTTPException)
async def http_error_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"status": "error", "error": {"code": "NOT_FOUND", "message": exc.detail or "invalid api route"}}
    )


@app.exception_handler(Exception)
async def global_error_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception in API route: %s", exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"status": "error", "error": {"code": "INTERNAL_SERVER_ERROR", "message": "internal server error"}}
    )