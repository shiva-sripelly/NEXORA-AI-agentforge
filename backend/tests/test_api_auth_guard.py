from fastapi.testclient import TestClient
from app.main import app
def test_anonymous_user_cannot_create_conversation():
 assert TestClient(app).post("/api/conversations",json={}).status_code==401
