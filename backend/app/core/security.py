from datetime import datetime, timedelta, timezone
from hashlib import sha256
from uuid import UUID

import jwt
from pwdlib import PasswordHash

from app.core.config import settings

password_hasher = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return password_hasher.verify(password, hashed)


def create_token(user_id: UUID, token_type: str, expires_delta: timedelta) -> tuple[str, datetime]:
    expires_at = datetime.now(timezone.utc) + expires_delta
    payload = {"sub": str(user_id), "type": token_type, "exp": expires_at, "iat": datetime.now(timezone.utc)}
    return jwt.encode(payload, settings.secret_key, algorithm="HS256"), expires_at


def decode_token(token: str, expected_type: str) -> UUID:
    payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
    if payload.get("type") != expected_type:
        raise jwt.InvalidTokenError("Incorrect token type")
    return UUID(payload["sub"])


def token_fingerprint(token: str) -> str:
    return sha256(token.encode()).hexdigest()
