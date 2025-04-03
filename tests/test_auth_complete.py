from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from main import app
from database import Base, get_db
from models import User
from security import get_password_hash

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
client = TestClient(app)

def test_successful_login():
    """Test successful login with valid credentials"""
    # Create a test user
    db = TestingSessionLocal()
    user = User(
        email="test@example.com",
        username="testuser",
        hashed_password=get_password_hash("testpass"),
        is_admin=False
    )
    db.add(user)
    db.commit()

    # Test login
    response = client.post(
        "/api/token",
        data={
            "username": "testuser",
            "password": "testpass",
            "grant_type": "password"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"

    # Clean up
    db.delete(user)
    db.commit()
    db.close()

def test_protected_route_with_token():
    """Test accessing protected route with valid token"""
    # Create a test user
    db = TestingSessionLocal()
    user = User(
        email="test@example.com",
        username="testuser",
        hashed_password=get_password_hash("testpass"),
        is_admin=False
    )
    db.add(user)
    db.commit()

    # Get token
    response = client.post(
        "/api/token",
        data={
            "username": "testuser",
            "password": "testpass",
            "grant_type": "password"
        }
    )
    token = response.json()["access_token"]

    # Test protected route
    response = client.get(
        "/users/me",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "testuser"
    assert data["email"] == "test@example.com"
    assert "id" in data
    assert "is_admin" in data

    # Clean up
    db.delete(user)
    db.commit()
    db.close()

def test_refresh_token():
    """Test refreshing access token"""
    # Create a test user
    db = TestingSessionLocal()
    user = User(
        email="test@example.com",
        username="testuser",
        hashed_password=get_password_hash("testpass"),
        is_admin=False
    )
    db.add(user)
    db.commit()

    # Get initial tokens
    response = client.post(
        "/api/token",
        data={
            "username": "testuser",
            "password": "testpass",
            "grant_type": "password"
        }
    )
    refresh_token = response.json()["refresh_token"]

    # Test token refresh
    response = client.post(
        "/api/token/refresh",
        json={"refresh_token": refresh_token}
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"

    # Clean up
    db.delete(user)
    db.commit()
    db.close()