from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
from jose import JWTError, jwt
from fastapi import HTTPException, status

class TokenManager:
    def __init__(self, secret_key: str, algorithm: str = "HS256"):
        self.secret_key = secret_key
        self.algorithm = algorithm
        self.access_token_expire_minutes = 30
        self.refresh_token_expire_days = 7

    def create_tokens(self, data: dict) -> Dict[str, str]:
        """Create both access and refresh tokens."""
        access_token = self._create_token(
            data=data,
            expires_delta=timedelta(minutes=self.access_token_expire_minutes)
        )
        refresh_token = self._create_token(
            data={**data, "refresh": True},
            expires_delta=timedelta(days=self.refresh_token_expire_days)
        )
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer"
        }

    def _create_token(self, data: dict, expires_delta: timedelta) -> str:
        """Create a token with expiration time."""
        to_encode = data.copy()
        expire = datetime.utcnow() + expires_delta
        to_encode.update({"exp": expire})
        return jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)

    def verify_token(self, token: str, refresh: bool = False) -> Tuple[bool, Optional[dict]]:
        """Verify a token and return its payload if valid."""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            
            # Check if token type matches (refresh token vs access token)
            is_refresh_token = payload.get("refresh", False)
            if refresh != is_refresh_token:
                return False, None

            # Check expiration
            exp = payload.get("exp")
            if not exp or datetime.fromtimestamp(exp) < datetime.utcnow():
                return False, None

            return True, payload
        except JWTError:
            return False, None

    def refresh_access_token(self, refresh_token: str) -> Dict[str, str]:
        """Create a new access token using a valid refresh token."""
        is_valid, payload = self.verify_token(refresh_token, refresh=True)
        if not is_valid or not payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired refresh token",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Remove refresh flag and create new access token
        del payload["refresh"]
        access_token = self._create_token(
            data=payload,
            expires_delta=timedelta(minutes=self.access_token_expire_minutes)
        )
        
        return {
            "access_token": access_token,
            "token_type": "bearer"
        }