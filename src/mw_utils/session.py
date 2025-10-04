import os
import secrets
import time
import logging
from typing import Optional, Dict, Any
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from .env import get_env_variable

logger = logging.getLogger("moodleware.sessions")

SESSION_COOKIE_NAME = "mng_session"
SESSION_MAX_AGE = int(get_env_variable("SESSION_MAX_AGE") or "14400")
SECRET_KEY = get_env_variable("SECRET_KEY") or secrets.token_urlsafe(32)

if not get_env_variable("SECRET_KEY"):
    logger.warning("SECRET_KEY not set! Using random key. Sessions will be invalidated on restart.")

serializer = URLSafeTimedSerializer(SECRET_KEY)
_sessions: Dict[str, Dict[str, Any]] = {}


class SessionData:
    def __init__(self, session_id: str, moodle_token: str, moodle_url: str, created_at: float):
        self.session_id = session_id
        self.moodle_token = moodle_token
        self.moodle_url = moodle_url
        self.created_at = created_at
        self.last_accessed = created_at


def create_session(moodle_token: str, moodle_url: str) -> str:
    session_id = secrets.token_urlsafe(32)
    _sessions[session_id] = {
        "moodle_token": moodle_token,
        "moodle_url": moodle_url,
        "created_at": time.time(),
        "last_accessed": time.time(),
    }
    logger.info(f"Created session {session_id[:8]}... for {moodle_url}")
    return serializer.dumps(session_id)


def get_session(signed_session_id: str) -> Optional[SessionData]:
    try:
        session_id = serializer.loads(signed_session_id, max_age=SESSION_MAX_AGE)
        session_data = _sessions.get(session_id)
        if not session_data:
            logger.warning(f"Session {session_id[:8]}... not found")
            return None
        
        session_data["last_accessed"] = time.time()
        return SessionData(
            session_id=session_id,
            moodle_token=session_data["moodle_token"],
            moodle_url=session_data["moodle_url"],
            created_at=session_data["created_at"]
        )
    except SignatureExpired:
        logger.info("Session expired")
        return None
    except BadSignature:
        logger.warning("Invalid session signature")
        return None
    except Exception as e:
        logger.error(f"Error retrieving session: {e}")
        return None


def delete_session(signed_session_id: str) -> bool:
    try:
        session_id = serializer.loads(signed_session_id, max_age=SESSION_MAX_AGE)
        
        if session_id in _sessions:
            del _sessions[session_id]
            logger.info(f"Deleted session {session_id[:8]}...")
            return True
        
        return False
        
    except Exception as e:
        logger.error(f"Error deleting session: {e}")
        return False


def cleanup_expired_sessions() -> int:
    now = time.time()
    expired = [sid for sid, data in _sessions.items() if now - data["created_at"] > SESSION_MAX_AGE]
    for session_id in expired:
        del _sessions[session_id]
    if expired:
        logger.info(f"Cleaned up {len(expired)} expired sessions")
    return len(expired)


def get_session_stats() -> Dict[str, Any]:
    return {
        "active_sessions": len(_sessions),
        "session_max_age": SESSION_MAX_AGE,
        "storage_type": "in-memory",
    }
