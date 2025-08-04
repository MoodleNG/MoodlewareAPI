# MoodlewareAPI

FastAPI application serving as a bridge to simplify interaction with the Moodle API, providing discoverable endpoints and clear parameter guidelines.

## Features

- **Configuration-driven**: All endpoints defined in `config.json`
- **Dynamic**: Automatically generates FastAPI routes from configuration
- **Docker Ready**: Easy deployment with Docker and docker-compose

## Structure

```
moodleapi/
├── config.json          # All endpoint definitions
├── main.py              # Dynamic FastAPI app generator
├── requirements.txt     # Dependencies
├── Dockerfile           # Docker container definition
├── docker-compose.yml   # Docker orchestration
├── .dockerignore        # Docker ignore file
├── .env.example         # Environment variables template
└── README.md            # This file
```

## Quick Start with Docker

### 🐳 Development (Simple)

```bash
# Build and run
docker-compose up -d --build
```

The API will be available at:
- **Direct**: http://localhost:8000
- **docs**: http://localhost:8000/redoc

## Manual Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Run the server:
```bash
python main.py
```

## Configuration

Just add entries to `config.json`:

```json
{
  "path": "/your/endpoint",
  "method": "POST",
  "function": "moodle_function_name",
  "name": "your_endpoint_name", 
  "description": "What this endpoint does",
  "tags": ["Category"],
  "params": [
    {
      "name": "param_name",
      "type": "str|int|bool|list|dict",
      "required": true|false,
      "default": "default_value",
      "description": "Parameter description"
    }
  ]
}
```

## Authentication

Use `/get-token` endpoint first to get your Moodle API token, then include `moodle_url` and `token` in subsequent requests.

## Configuration Format

- **path**: URL path for the endpoint
- **method**: HTTP method (GET, POST, etc.)
- **function**: Moodle web service function name (or "auth"/"universal" for special handlers)
- **name**: Internal name for the endpoint
- **description**: Human-readable description
- **tags**: Array of tags for grouping in docs
- **params**: Array of parameter definitions
