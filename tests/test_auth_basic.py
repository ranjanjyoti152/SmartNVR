from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_login_invalid_credentials():
    """Test login with invalid credentials"""
    response = client.post(
        "/api/token",
        data={
            "username": "nonexistent",
            "password": "wrong",
            "grant_type": "password"  # Required for OAuth2 password flow
        }
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect username or password"

def test_protected_route_no_token():
    """Test accessing protected route without token"""
    response = client.get("/users/me")
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"