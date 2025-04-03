import pytest
from fastapi.testclient import TestClient
from main import app
from security import register_user, add_camera, log_detection_event
from database import SessionLocal, get_db
from models import User, Camera, DetectionEvent

@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c

@pytest.fixture
def db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def test_register_user(db):
    response = register_user(db, "test@example.com", "testuser", "Password123!")
    assert response.email == "test@example.com"
    assert response.username == "testuser"

def test_add_camera(db):
    user = register_user(db, "test@example.com", "testuser", "Password123!")
    response = add_camera(db, "Test Camera", "rtsp://testcamera", user.id)
    assert response.name == "Test Camera"
    assert response.rtsp_url == "rtsp://testcamera"

def test_log_detection_event(db):
    camera = add_camera(db, "Test Camera", "rtsp://testcamera", 1)
    response = log_detection_event(db, camera.id, "person", 0.95, {"x": 10, "y": 10, "width": 100, "height": 100})
    assert response.object_type == "person"
    assert response.confidence == 0.95
