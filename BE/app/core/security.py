from datetime import datetime, timedelta, timezone

from cryptography.fernet import Fernet
from jose import JWTError, jwt

from app.core.config import get_settings

settings = get_settings()


def create_session_token(user_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": user_id, "exp": expire}
    return jwt.encode(payload, settings.app_secret_key, algorithm=settings.jwt_algorithm)


def decode_session_token(token: str) -> str | None:
    try:
        payload = jwt.decode(token, settings.app_secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError:
        return None
    return payload.get("sub")


def _fernet() -> Fernet:
    key = settings.token_encryption_key
    if not key:
        raise RuntimeError("TOKEN_ENCRYPTION_KEY is not set — generate one with Fernet.generate_key()")
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt_token(raw_token: str) -> str:
    """Encrypt a GitLab OAuth token before persisting it (PRD Section 14: encrypted at rest)."""
    return _fernet().encrypt(raw_token.encode()).decode()


def decrypt_token(encrypted_token: str) -> str:
    return _fernet().decrypt(encrypted_token.encode()).decode()
