import os
import secrets
import time
import logging
import json
from typing import Optional, Dict, Any
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from redis.asyncio import Redis, ConnectionPool
from .env import get_env_variable

logger = logging.getLogger("moodleware.sessions")

SESSION_COOKIE_NAME = "mng_session"
SESSION_MAX_AGE = int(get_env_variable("SESSION_MAX_AGE") or "14400")
SECRET_KEY = get_env_variable("SECRET_KEY") or secrets.token_urlsafe(32)
REDIS_URL = get_env_variable("REDIS_URL") or "redis://localhost:6379/0"

if not get_env_variable("SECRET_KEY"):
    logger.warning("SECRET_KEY not set! Using random key. Sessions will be invalidated on restart.")

serializer = URLSafeTimedSerializer(SECRET_KEY)

# Redis client (initialized in app.py lifespan)
_redis_client: Optional[Redis] = None


def init_redis(redis_client: Redis):
    """Initialize Redis client for session storage."""
    global _redis_client
    _redis_client = redis_client
    logger.info(f"Redis session storage initialized: {REDIS_URL}")


def get_redis() -> Redis:
    """Get Redis client instance."""
    if _redis_client is None:
        raise RuntimeError("Redis client not initialized. Call init_redis() first.")
    return _redis_client


class SessionData:
    def __init__(self, session_id: str, moodle_token: str, moodle_url: str, created_at: float):
        self.session_id = session_id
        self.moodle_token = moodle_token
        self.moodle_url = moodle_url
        self.created_at = created_at
        self.last_accessed = created_at


async def create_session(moodle_token: str, moodle_url: str) -> str:
    redis = get_redis()
    session_id = secrets.token_urlsafe(32)
    
    session_data = {
        "moodle_token": moodle_token,
        "moodle_url": moodle_url,
        "created_at": time.time(),
        "last_accessed": time.time(),
    }
    
    # Store in Redis with automatic expiration
    await redis.setex(
        f"session:{session_id}",
        SESSION_MAX_AGE,
        json.dumps(session_data)
    )
    
    logger.info(f"Created session {session_id[:8]}... for {moodle_url}")
    return serializer.dumps(session_id)


async def get_session(signed_session_id: str) -> Optional[SessionData]:
    try:
        redis = get_redis()
        session_id = serializer.loads(signed_session_id, max_age=SESSION_MAX_AGE)
        
        # Retrieve from Redis
        data = await redis.get(f"session:{session_id}")
        if not data:
            logger.warning(f"Session {session_id[:8]}... not found in Redis")
            return None
        
        session_data = json.loads(data)
        
        # Update last_accessed timestamp
        session_data["last_accessed"] = time.time()
        await redis.setex(
            f"session:{session_id}",
            SESSION_MAX_AGE,
            json.dumps(session_data)
        )
        
        return SessionData(
            session_id=session_id,
            moodle_token=session_data["moodle_token"],
            moodle_url=session_data["moodle_url"],
            created_at=session_data["created_at"]
        )
    except SignatureExpired:
        logger.info("Session signature expired")
        return None
    except BadSignature:
        logger.warning("Invalid session signature")
        return None
    except Exception as e:
        logger.error(f"Error retrieving session: {e}")
        return None


async def delete_session(signed_session_id: str) -> bool:
    try:
        redis = get_redis()
        session_id = serializer.loads(signed_session_id, max_age=SESSION_MAX_AGE)
        
        # Delete from Redis
        deleted = await redis.delete(f"session:{session_id}")
        
        if deleted > 0:
            logger.info(f"Deleted session {session_id[:8]}...")
            return True
        
        logger.warning(f"Session {session_id[:8]}... not found for deletion")
        return False
        
    except Exception as e:
        logger.error(f"Error deleting session: {e}")
        return False


async def cleanup_expired_sessions() -> int:
    """
    Redis automatically expires sessions via SETEX.
    This function is kept for compatibility but does nothing as cleanup is automatic.
    Returns 0 since Redis handles expiration internally.
    """
    return 0


async def get_session_stats() -> Dict[str, Any]:
    redis = get_redis()
    
    # Count sessions by scanning for session:* keys
    session_keys = []
    async for key in redis.scan_iter(match="session:*"):
        session_keys.append(key)
    
    return {
        "active_sessions": len(session_keys),
        "session_max_age": SESSION_MAX_AGE,
        "storage_type": "redis",
        "redis_url": REDIS_URL,
    }
