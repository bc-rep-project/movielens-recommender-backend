# JWT verification logic (Supabase)
# backend/app/core/security.py

import logging
from typing import Dict, Optional, Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from jose.exceptions import ExpiredSignatureError, JWTClaimsError

# Import the singleton settings instance from config.py
from app.core.config import settings

logger = logging.getLogger(__name__)

# Scheme for extracting "Bearer <token>" from Authorization header
# auto_error=False means we handle the error manually if token is missing/malformed
token_bearer_scheme = HTTPBearer(auto_error=False)

# --- Custom Exceptions (Optional, but can provide clearer error types) ---
class CredentialsException(HTTPException):
    def __init__(self, detail: str = "Could not validate credentials", status_code: int = status.HTTP_401_UNAUTHORIZED):
        super().__init__(
            status_code=status_code,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )

class TokenExpiredException(CredentialsException):
    def __init__(self, detail: str = "Token has expired"):
        super().__init__(detail=detail, status_code=status.HTTP_401_UNAUTHORIZED)

class InvalidTokenException(CredentialsException):
    def __init__(self, detail: str = "Invalid token signature or format"):
        super().__init__(detail=detail, status_code=status.HTTP_401_UNAUTHORIZED)

class InvalidClaimsException(CredentialsException):
    def __init__(self, detail: str = "Invalid token claims (e.g., audience, issuer)"):
        super().__init__(detail=detail, status_code=status.HTTP_401_UNAUTHORIZED)

class MissingTokenException(CredentialsException):
     def __init__(self, detail: str = "Authentication token missing"):
        super().__init__(detail=detail, status_code=status.HTTP_401_UNAUTHORIZED)

class InsufficientPermissionsException(CredentialsException):
     def __init__(self, detail: str = "Insufficient permissions"):
        super().__init__(detail=detail, status_code=status.HTTP_403_FORBIDDEN)


# --- Core Verification Logic ---

async def verify_token(
    auth_credentials: Optional[HTTPAuthorizationCredentials] = Depends(token_bearer_scheme),
) -> Dict[str, Any]:
    """
    Verifies the Supabase JWT token from the Authorization header.

    Args:
        auth_credentials: The credentials extracted by HTTPBearer (contains scheme and credentials).

    Returns:
        The decoded JWT payload as a dictionary if valid.

    Raises:
        MissingTokenException: If no token is provided or format is wrong.
        TokenExpiredException: If the token signature has expired.
        InvalidClaimsException: If claims like audience or issuer are invalid.
        InvalidTokenException: If the token signature or format is generally invalid.
        CredentialsException: For other validation errors.
    """
    if auth_credentials is None or not auth_credentials.credentials:
        logger.warning("Authentication attempt failed: No token provided in Authorization header.")
        raise MissingTokenException()

    token = auth_credentials.credentials
    try:
        # Construct issuer URL if needed for validation (optional)
        # issuer = f"{settings.SUPABASE_URL}/auth/v1" if settings.SUPABASE_URL else None
        issuer = None # Set this based on settings.JWT_ISSUER if configured

        payload = jwt.decode(
            token,
            settings.SUPABASE_JWT_SECRET.get_secret_value(), # Use .get_secret_value() for SecretStr
            algorithms=[settings.JWT_ALGORITHM],
            audience=settings.JWT_AUDIENCE,
            issuer=issuer, # Optional: validates the 'iss' claim if issuer is set
            options={
                "verify_signature": True,
                "verify_aud": True,
                "verify_exp": True,
                "verify_iss": issuer is not None, # Only verify if issuer is configured
                # Add leeway for clock skew if needed:
                # "leeway": 60 # seconds
            }
        )
        # Token is valid and claims match (aud, exp, iss if checked)
        return payload

    except ExpiredSignatureError:
        logger.warning("Authentication attempt failed: Token expired.")
        raise TokenExpiredException()
    except JWTClaimsError as e:
        logger.warning(f"Authentication attempt failed: Invalid claims - {e}")
        # Provide specific claim error if possible
        raise InvalidClaimsException(detail=f"Invalid token claims: {e}")
    except JWTError as e:
        logger.warning(f"Authentication attempt failed: Invalid token format or signature - {e}")
        raise InvalidTokenException(detail=f"Invalid token: {e}")
    except Exception as e:
        # Catch unexpected errors during validation
        logger.error(f"Unexpected error during token validation: {e}", exc_info=True)
        # Return a generic credentials exception for security
        raise CredentialsException()


# --- FastAPI Dependencies ---

async def get_current_user_payload(
    payload: Dict[str, Any] = Depends(verify_token)
) -> Dict[str, Any]:
    """
    FastAPI dependency that verifies the token and returns the full payload.
    Useful if you need multiple claims (email, roles, etc.) in your endpoint.
    """
    return payload


async def get_current_user_id(
    payload: Dict[str, Any] = Depends(verify_token)
) -> str:
    """
    FastAPI dependency that verifies the token and returns the user ID ('sub' claim).
    This is often the primary identifier needed by endpoints.

    Raises:
        CredentialsException: If the 'sub' claim is missing from the token payload.
    """
    user_id = payload.get("sub")
    if user_id is None:
        logger.error("Authentication failed: 'sub' claim (user ID) missing from token payload.")
        # Use a generic error message for security
        raise CredentialsException(detail="User identifier not found in token")
    if not isinstance(user_id, str):
         logger.error(f"Authentication failed: 'sub' claim is not a string (type: {type(user_id)}).")
         raise CredentialsException(detail="Invalid user identifier format in token")

    return user_id