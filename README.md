# <p align="center">MoodlewareAPI</p>
<p align="center">
  <img src="./assets/MoodlewareAPI_logo.png" width="200" alt="MoodlewareAPI Logo">
</p>
<p align="center">
  <strong>A FastAPI bridge that simplifies interaction with the Moodle API, providing discoverable endpoints and clear parameter guidelines.</strong>
  Built with FastAPI and Docker.
</p>
<p align="center">
  <a href="https://github.com/MyDrift-user/MoodlewareAPI"><img src="https://badgetrack.pianonic.ch/badge?tag=moodleware-api&label=visits&color=3644b7&style=flat" alt="visits" </a>
  <a href="https://github.com/MyDrift-user/MoodlewareAPI/blob/main/LICENSE"><img src="https://img.shields.io/github/license/MyDrift-user/MoodlewareAPI?color=3644b7&label=License"/></a>
  <a href="https://github.com/MyDrift-user/MoodlewareAPI/releases"><img src="https://img.shields.io/github/v/release/MyDrift-user/MoodlewareAPI?include_prereleases&color=3644b7&label=Latest%20Release"/></a>
  <a href="#-installation"><img src="https://img.shields.io/badge/Selfhost-Instructions-3644b7.svg"/></a>
</p>

## 🚀 Features
- **Configuration-driven**: All endpoints defined in `config.json`
- **Dynamic Routes**: Automatically generates FastAPI routes from configuration
- **Authentication Flow**: Built-in token management for Moodle API
- **Auto Documentation**: Interactive API docs with Swagger/ReDoc
- **Docker Ready**: Easy deployment with Docker and docker-compose
- **Type Safety**: Full parameter validation and type checking

## 📦 Installation

### Using Docker (Recommended)

#### Option 1: Pull and Run a Pre-built Image
```bash
docker pull mydrift-user/moodlewareapi:latest
```

Then, run the container:
```bash
docker run -d -p 8000:8000 --name moodlewareapi mydrift-user/moodlewareapi:latest
```
The API will be available at [http://localhost:8000](http://localhost:8000).

#### Option 2: Run with Docker Compose
**1. Create a `compose.yaml` file:**
```yaml
services:
  moodlewareapi:
    image: mydrift-user/moodlewareapi:latest
    ports:
      - "8000:8000"
    restart: unless-stopped
    environment:
      - MOODLE_URL=https://your-moodle-site.com
```

**2. Start it:**
```bash
docker compose up -d --build
```

The API will be available at:
- **Direct**: [http://localhost:8000](http://localhost:8000)
- **Interactive Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)

### Manual Installation

```bash
# Clone the repository
git clone https://github.com/MyDrift-user/MoodlewareAPI.git
cd MoodlewareAPI

# Create a virtual environment
python -m venv venv
# On Linux/macOS:
source venv/bin/activate
# On Windows:
# venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the application
python asgi.py
```
The API will be available at [http://localhost:8000](http://localhost:8000).

## 🛠️ Usage

### 1. Get Authentication Token
```bash
curl -X POST "http://localhost:8000/get-token" \
  -H "Content-Type: application/json" \
  -d '{"moodle_url": "https://your-moodle.com", "username": "your-username", "password": "your-password"}'
```

### 2. Use API Endpoints
Include `moodle_url` and `token` in subsequent requests to access Moodle functions through simplified endpoints.

## ⚙️ Configuration

Add endpoints to `config.json`:

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
      "required": true,
      "default": "default_value",
      "description": "Parameter description"
    }
  ]
}
```

### Configuration Fields
- **path**: URL path for the endpoint
- **method**: HTTP method (GET, POST, etc.)
- **function**: Moodle web service function name (or "auth"/"universal" for special handlers)
- **name**: Internal name for the endpoint
- **description**: Human-readable description
- **tags**: Array of tags for grouping in docs
- **params**: Array of parameter definitions with type validation

## 📋 Requirements
- Python 3.13+
- Docker (optional)
- Dependencies: Listed in [requirements.txt](./requirements.txt)

## 📜 License
This project is licensed under the MIT License.
See the [LICENSE](LICENSE) file for more details.

---
<p align="center">Made with ❤️ by <a href="https://github.com/MyDrift-user">MyDrift</a></p>
