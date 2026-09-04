from uuid import uuid4
from app.core.security import create_token, decode_token, hash_password, verify_password
from datetime import timedelta


def test_password_hash_and_token_roundtrip():
    password = "SecurePass1"
    hashed = hash_password(password)
    assert hashed != password and verify_password(password, hashed)
    user_id = uuid4(); token, _ = create_token(user_id, "access", timedelta(minutes=1))
    assert decode_token(token, "access") == user_id
