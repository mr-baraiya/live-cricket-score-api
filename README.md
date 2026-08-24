# Live Cricket Score & Commentary API

A clean, modular Python FastAPI project that scrapes publicly accessible Cricbuzz pages and exposes normalized JSON APIs for live match tracking, scorecards, ball-by-ball commentary, and change detection.

---

## Disclaimer & Legal Usage Note

- **Not an official API provided by Cricbuzz.**
- This project retrieves data by scraping publicly available web content from Cricbuzz and is **not affiliated with, authorized, sponsored, or endorsed by Cricbuzz**.
- This project is created **for development, learning, and personal experimentation purposes only**.
- While this scraper source code itself is licensed under the MIT License, the underlying Cricbuzz match data, team names, trademarks, and commentary text remain the property of their respective owners and are **not licensed for public or commercial redistribution**.
- All credits go to **[Cricbuzz](https://www.cricbuzz.com/)**.

---

## Features 🚀

- **Modular Architecture**: Complete separation of HTTP client (`scraper/client.py`), fallback selector registry (`scraper/selectors.py`), safe parsers (`scraper/event_parser.py`), Pydantic data models (`models/`), caching and change detection (`services/`), and FastAPI routes (`app.py`).
- **Robust Event Classification**: Categorizes deliveries into `DOT`, `SINGLE`, `TWO`, `THREE`, `FOUR`, `FIVE`, `SIX`, `WIDE`, `NO_BALL`, `BYE`, `LEG_BYE`, `WICKET`, `PENALTY`, `UNKNOWN`.
- **5-Run Delivery Support**: Accurately extracts 5-run deliveries (`FIVE`, `runs: 5`).
- **False-WICKET Protection**: Strict dismissal keyword matching prevents false LBW appeals or umpire's calls from being misclassified as wickets.
- **Deterministic `event_id`**: Generates a stable unique delivery identifier (`matchId-innings-over.ball-hash`).
- **Last Known Good Data**: Preserves valid match data during temporary network errors and flags responses as `data_status: "stale"`.
- **Active Players & Innings Tracking**: Extracts all batting rows, `current_batsmen`, `current_bowler`, and `innings` details.
- **Real-Time Change Detector**: `GET /match/{id}/changes` detects new deliveries, boundaries, wickets, and score updates.
- **Swagger Documentation**: Self-hosted UI at `/docs`.

---

## Project Structure

```text
live-cricket-score-api/
│
├── app.py                      # FastAPI App Routing & Middleware
├── cli.py                      # CLI Tool
├── requirements.txt            # Package Dependencies
├── run.py                      # Server Launcher
│
├── scraper/                    # Web Scraper Layer
│   ├── client.py               # Async HTTP Client (httpx, retries)
│   ├── selectors.py            # Centralized Selectors with Fallbacks
│   ├── parser_utils.py         # Safe text/type parsers & team extractor
│   ├── event_parser.py         # Delivery event classifier & dismissal parser
│   ├── matches.py              # Live & Upcoming match discovery scraper
│   ├── match.py                # Match overview scraper
│   ├── scorecard.py            # Scorecard scraper
│   └── commentary.py           # Ball-by-ball commentary scraper
│
├── models/                     # Normalized Pydantic Models
│   ├── match.py                # MatchInfo, LiveMatchesResponse, ScorecardResponse, FullMatchResponse
│   ├── score.py                # ScoreInfo
│   ├── player.py               # Batsman & Bowler models
│   ├── commentary.py           # CommentaryItem, ChangeDetectionResult
│   └── health.py               # HealthStatusResponse
│
├── services/                   # Business Logic & Service Layer
│   ├── cache.py                # Short-TTL in-memory cache
│   ├── change_detector.py      # Delivery deduplication & change detector
│   └── match_service.py        # Service orchestrator & Last Known Good Data
│
└── tests/                      # Automated Unit Tests
    ├── fixtures/               # HTML Test Fixtures
    ├── test_parser.py
    ├── test_event_parser.py
    └── test_change_detector.py
```

---

## REST API Endpoints

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/` | API status metadata |
| `GET` | `/health` | Dynamic scraper health status |
| `GET` | `/matches/live` | Currently live matches |
| `GET` | `/matches/upcoming` | Scheduled match previews |
| `GET` | `/match/{id}` | High-level match overview |
| `GET` | `/match/{id}/scorecard` | Detailed match scorecard |
| `GET` | `/match/{id}/commentary` | Ball-by-ball live commentary |
| `GET` | `/match/{id}/recent` | Latest commentary event |
| `GET` | `/match/{id}/full` | Combined match & commentary payload |
| `GET` | `/match/{id}/changes` | Real-time delta & new delivery detector |

---

## Setup & Running

### 1. Installation

```sh
# Clone repository
git clone https://github.com/mskian/live-cricket-score-api
cd live-cricket-score-api

# Create & activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: .\venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Start Development Server

```sh
python run.py
# or: uvicorn app:app --host 0.0.0.0 --port 6020
```

### 3. Run Automated Tests

```sh
python -m unittest discover -s tests
```

---

## CLI Usage

```sh
# List live matches
python cli.py --live

# List upcoming matches
python cli.py --upcoming

# Fetch match overview
python cli.py 163017

# Fetch detailed scorecard
python cli.py 163017 --scorecard

# Fetch commentary feed
python cli.py 163017 --commentary

# Fetch latest event
python cli.py 163017 --recent

# Fetch full combined payload
python cli.py 163017 --full

# Detect real-time changes
python cli.py 163017 --changes
```

---

## Vercel Deployment

1. **Install Vercel CLI**:
   ```sh
   npm install -g vercel
   ```

2. **Login to Vercel**:
   ```sh
   vercel login
   ```

3. **Deploy Preview**:
   ```sh
   vercel
   ```

4. **Deploy Production**:
   ```sh
   vercel --prod
   ```

---

## Serverless Limitations

- **Request-Based Execution**: This backend runs as request-based serverless functions on Vercel. It is **not** a 24/7 background scraper process.
- **In-Memory Cache & Change Detection**: In-memory caching and change detection on `GET /match/{id}/changes` operate on a best-effort basis per serverless container instance.
- **VPS Portability**: The codebase preserves complete architecture separation (`app.py`, `services/`, `scraper/`), making it simple to deploy on a persistent VPS (using Uvicorn/Systemd) if continuous polling for live streams is needed later.

---

## License

MIT License - see the [LICENSE](LICENSE) file for details.
