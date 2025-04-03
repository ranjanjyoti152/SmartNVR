import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from datetime import timedelta

from database import Base, get_db
from main import app
from models import User
from security import get_password_hash, token_manager

# Create test database
SQLALCHEMY_DATABASE_URL = "sqlite://"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

# Create test client
from fastapi.testclient import TestClient as FastAPITestClient
client = FastAPITestClient(app)

@pytest.fixture
def test_db():
    Base.metadata.create_all(bind=engine)
    yield TestingSessionLocal()
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def test_user(test_db):
    user = User(
        email="test@example.com",
        username="testuser",
        hashed_password=get_password_hash("testpassword"),
        is_admin=False
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    return user

def test_create_user(test_db):
    response = client.post(
        "/users/",
        json={
            "email": "new@example.com",
            "username": "newuser",
            "password": "newpassword"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "new@example.com"
    assert data["username"] == "newuser"
    assert "hashed_password" not in data

def test_login_success(test_user):
    response = client.post(
        "/api/token",
        data={
            "username": "testuser",
            "password": "testpassword"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"

def test_login_invalid_password(test_user):
    response = client.post(
        "/api/token",
        data={
            "username": "testuser",
            "password": "wrongpassword"
        }
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect username or password"

def test_protected_route(test_user):
    # First login to get token
    login_response = client.post(
        "/api/token",
        data={
            "username": "testuser",
            "password": "testpassword"
        }
    )
    token = login_response.json()["access_token"]
    
    # Test protected route with valid token
    response = client.get(
        "/users/me",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "testuser"

def test_protected_route_no_token():
    response = client.get("/users/me")
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"

def test_refresh_token(test_user):
    # First login to get tokens
    login_response = client.post(
        "/api/token",
        data={
            "username": "testuser",
            "password": "testpassword"
        }
    )
    refresh_token = login_response.json()["refresh_token"]
    
    # Test token refresh
    response = client.post(
        "/api/token/refresh",
        headers={"Authorization": f"Bearer {refresh_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"

def test_refresh_token_invalid():
    response = client.post(
        "/api/token/refresh",
        headers={"Authorization": "Bearer invalid_token"}
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Could not refresh token"

def test_token_expiration(test_user):
    # Create an expired token
    expired_token = token_manager._create_token(
        data={"sub": "testuser"},
        expires_delta=timedelta(seconds=-1)
    )
    
    # Test protected route with expired token
    response = client.get(
        "/users/me",
        headers={"Authorization": f"Bearer {expired_token}"}
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Could not validate credentials"