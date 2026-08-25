# Live Cricket Score & Commentary API

A clean, modular Python FastAPI project that fetches publicly accessible live cricket match data and exposes normalized JSON APIs and real-time WebSockets for live match tracking, scorecards, commentary, stadium background uploading, and OBS broadcast synchronization.

---

## Key Features

- **FastAPI Core & WebSockets**: Low-latency REST endpoints and `/ws/match/{match_id}` WebSocket broadcasting engine.
- **Stadium Background Engine**:
  - `POST /stadium/upload`: Upload custom 16:9 stadium backdrop photos.
  - Automatic WebP conversion, 1920×1080 resolution resize, and file size optimization (&lt;250 KB).
  - Vercel Blob CDN upload with automatic local static file storage fallback (`/static/stadium_background.webp`).
  - Real-time WebSocket broadcasting (`stadium_background_updated`) across active broadcast screens.
- **Robust Event Classification**: Categorizes deliveries into `DOT`, `SINGLE`, `TWO`, `THREE`, `FOUR`, `FIVE`, `SIX`, `WIDE`, `NO_BALL`, `BYE`, `LEG_BYE`, `WICKET`.
- **False-WICKET Protection**: Strict dismissal keyword parsing prevents false LBW appeals or umpire's calls from being misclassified.
- **Last Known Good Data**: Preserves valid match data during temporary network interruptions.
- **Swagger Documentation**: Interactive API documentation at `/docs`.

---

## API Endpoint Reference

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/` | API status metadata |
| `GET` | `/health` | Dynamic scraper health check |
| `GET` | `/matches/live` | Currently live matches |
| `GET` | `/matches/upcoming` | Scheduled match previews |
| `GET` | `/match/{id}` | High-level match overview |
| `GET` | `/match/{id}/scorecard` | Detailed match scorecard |
| `GET` | `/match/{id}/commentary` | Ball-by-ball commentary |
| `GET` | `/match/{id}/full` | Complete match data snapshot |
| `GET` | `/match/{id}/control` | Current OBS broadcast control state |
| `POST` | `/match/{id}/control` | Update broadcast layout & element toggles |
| `GET` | `/stadium/background` | Get active stadium backdrop settings |
| `POST` | `/stadium/upload` | Upload & optimize stadium background photo |
| `WS` | `/ws/match/{id}` | Real-time WebSocket broadcast feed |

---

## Running the API Locally

```bash
# Navigate to API directory
cd live-cricket-score-api

# Install dependencies
pip install -r requirements.txt

# Start the server on port 6020
python run.py
```

The server will be active at `http://localhost:6020`.

---

## License

This project is licensed under the [MIT License](LICENSE).
