# Simple Moodle API Proxy

A clean, configuration-driven FastAPI proxy for Moodle Web Services with Docker support.

## Features

- **Configuration-driven**: All endpoints defined in `config.json`
- **Dynamic**: Automatically generates FastAPI routes from configuration
- **Scalable**: Easy to add new endpoints by just updating config
- **Docker Ready**: Easy deployment with Docker and docker-compose

## Structure

```
moodleapi/
├── config.json          # All endpoint definitions
├── main.py              # Dynamic FastAPI app generator
├── requirements.txt     # Dependencies
├── Dockerfile           # Docker container definition
├── docker-compose.yml   # Docker orchestration
├── nginx.conf           # Nginx reverse proxy config
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

**Hot reload**: If you mount the config file as a volume, restart the container to load changes:

```bash
docker-compose restart moodle-api
```

## Production Deployment

### With SSL/HTTPS

1. Add your SSL certificates to `ssl/` folder
2. Uncomment HTTPS section in `nginx.conf`
3. Update domain name in nginx config
4. Run with production profile:

```bash
docker-compose --profile production up -d
```

## Docker Commands

```bash
# Build only
docker-compose build

# View logs
docker-compose logs -f moodle-api

# Stop services
docker-compose down

# Stop and remove volumes
docker-compose down -v

# Update config without rebuilding
docker-compose restart moodle-api
```

## Health Monitoring

Health check endpoint: `/health`

```bash
# Check if service is healthy
curl http://localhost:8000/health

# Response
{
  "status": "healthy",
  "service": "Moodle API Proxy", 
  "version": "2.0.0",
  "endpoints_loaded": 30
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
