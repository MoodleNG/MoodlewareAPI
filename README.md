# <p align="center">MoodlewareAPI</p>
<p align="center">
  <img src="./assets/MoodlewareAPI_logo.png" width="200" alt="MoodlewareAPI Logo">
</p>
<p align="center">
  <strong>A FastAPI bridge that simplifies interaction with the Moodle API, providing discoverable endpoints and clear parameter guidelines.</strong>
  Built with FastAPI and Docker.
</p>
<p align="center">
  <a href="https://github.com/MyDrift-user/MoodlewareAPI"><img src="https://badgetrack.pianonic.ch/badge?tag=moodleware-api&label=visits&color=3644b7&style=flat" alt="visits"/></a>
  <a href="https://github.com/MyDrift-user/MoodlewareAPI/blob/main/LICENSE"><img src="https://img.shields.io/github/license/MyDrift-user/MoodlewareAPI?color=3644b7&label=License"/></a>
  <a href="https://github.com/MyDrift-user/MoodlewareAPI/releases"><img src="https://img.shields.io/github/v/release/MyDrift-user/MoodlewareAPI?include_prereleases&color=3644b7&label=Latest%20Release"/></a>
  <a href="#-installation"><img src="https://img.shields.io/badge/Selfhost-Instructions-3644b7.svg"/></a>
</p>

## 🚀 Features
- Configuration-driven via `config.json`
- Dynamic FastAPI routes generated from config
- Built-in token retrieval endpoint
- Interactive API docs (Swagger UI)
- Docker-ready

## 📦 Run

### Docker
Use the included `compose.yaml` or run the image directly.

Docker Compose (recommended):
```yaml
services:
  moodlewareapi:
    build: .
    ports:
      - "8000:8000"
    restart: unless-stopped
    environment:
      # Option A: Fixed Moodle URL for all requests
      - MOODLE_URL=https://moodle.example.edu
      # Option B: Per-request Moodle URL (set to * or leave empty)
      # - MOODLE_URL=*
      - ALLOW_ORIGINS=*
      - LOG_LEVEL=info
```
Start:
```bash
docker compose up -d --build
```

### Manual
```bash
pip install -r requirements.txt
python asgi.py
```

Service URLs:
- Swagger UI: http://localhost:8000/
- Health: http://localhost:8000/healthz

## 🛠️ Usage

### 1) Get a Moodle token
- If `MOODLE_URL` is unset or `*`, include `moodle_url` in the query.
- If `MOODLE_URL` is a real URL, `moodle_url` is not required.

Example (per-request Moodle URL):
```bash
curl "http://localhost:8000/auth?moodle_url=https://moodle.school.edu&username=USER&password=PASS&service=moodle_mobile_app"
```

### 2) Call Moodle functions via REST proxy
Provide the token either via Authorization header or `?wstoken=`. 

Example using Authorization header (with preconfigured MOODLE_URL):
```bash
curl -H "Authorization: Bearer YOUR_TOKEN" "http://localhost:8000/core_webservice_get_site_info"
```

Example using query parameter (with preconfigured MOODLE_URL):
```bash
curl "http://localhost:8000/core_webservice_get_site_info?wstoken=YOUR_TOKEN"
```

Notes:
- When `ALLOW_ORIGINS=*`, credentials are disabled per CORS spec.
- Each response includes passthrough headers `X-Moodle-Direct-URL` and `X-Moodle-Direct-Method` for debugging.

## ⚙️ Environment
- `MOODLE_URL`
  - Set to a full base URL (e.g., `https://moodle.example.com`) to use it for all requests, or
  - Set to `*` or leave empty to require `moodle_url` per request.
- `PORT` (default 8000)
- `ALLOW_ORIGINS` (comma-separated; `*` allows all without credentials)
- `LOG_LEVEL` (`critical|error|warning|info|debug`, default `info`)

## 🔧 Config (`config.json`)
Minimal shape of an entry:
```json
{
  "path": "/core_webservice_get_site_info",
  "method": "GET",
  "function": "core_webservice_get_site_info",
  "description": "Get Moodle site information & user information",
  "tags": ["Core"],
  "query_params": [
    {
      "name": "userid",
      "type": "int",
      "required": false,
      "description": "User ID"
    }
  ],
  "responses": {
    "200": {
      "description": "OK"
    }
  }
}
```
- `path`: Path added under the Moodle base URL
- `method`: HTTP method
- `function`: Moodle wsfunction name (auto-added for `/webservice/rest/server.php`)
- `description`, `tags`: For docs grouping
- `query_params`: Parameter list with `name`, `type` (str|int|bool|float|double|list), `required`, `default`, `description`
- `responses`: Optional OpenAPI response metadata

## 📋 Requirements
- Python (see `requirements.txt`)
- Docker (optional)

## 📄 License
MIT. See `LICENSE`.

---
<p align="center">Made with ❤️ by <a href="https://github.com/mydrift-user">MyDrift</a></p>