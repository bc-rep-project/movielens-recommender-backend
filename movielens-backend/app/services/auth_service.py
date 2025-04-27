import logging
from typing import Optional, Dict, Any
from supabase import create_client, Client
from supabase.lib.client_options import ClientOptions

from app.core.config import settings
from app.models.auth import UserCreate, UserLogin, AuthResponse, TokenData, UserRead, RegisterResponse

logger = logging.getLogger(__name__)

class AuthServiceError(Exception):
    """Custom exception for Auth service errors."""
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)

class AuthService:
    def __init__(self):
        self.supabase_url: str = str(settings.SUPABASE_URL)
        self.supabase_key: str = settings.SUPABASE_ANON_KEY.get_secret_value()
        # Initialize client lazily
        self._client: Optional[Client] = None

    def _get_client(self) -> Client:
        """Initializes and returns the Supabase client."""
        if self._client is None:
            logger.info("Initializing Supabase client...")
            opts = ClientOptions(
                auto_refresh_token=True,
                persist_session=False
            )
            self._client = create_client(self.supabase_url, self.supabase_key, options=opts)
            logger.info("Supabase client initialized.")
        return self._client

    async def register_user(self, user_data: UserCreate) -> RegisterResponse:
        """Registers a new user with Supabase."""
        client = self._get_client()
        try:
            logger.info(f"Attempting to register user: {user_data.email}")
            
            # Prepare user metadata
            user_metadata = {}
            if user_data.full_name:
                user_metadata['full_name'] = user_data.full_name
            
            # Register user with Supabase
            res = client.auth.sign_up({
                "email": user_data.email,
                "password": user_data.password,
                "options": {
                    "data": user_metadata
                } if user_metadata else {}
            })

            if res.user:
                logger.info(f"Successfully registered user: {res.user.id} ({res.user.email})")
                return RegisterResponse(
                    user_id=str(res.user.id),
                    email=res.user.email
                )
            else:
                # This case might indicate an unexpected response format from Supabase
                logger.error(f"Supabase registration response missing user data for {user_data.email}. Response: {res}")
                raise AuthServiceError("Registration failed due to an unexpected Supabase response.", 500)

        except Exception as e:
            logger.error(f"Error during user registration: {e}", exc_info=True)
            
            # Handle specific error cases
            error_message = str(e).lower()
            if "already registered" in error_message or "already exists" in error_message:
                raise AuthServiceError(f"User with email {user_data.email} already exists.", 409)  # 409 Conflict
            
            # Generic error case
            raise AuthServiceError(f"Registration failed: {str(e)}", 500)

    async def login_user(self, login_data: UserLogin) -> AuthResponse:
        """Logs in a user with email and password using Supabase."""
        client = self._get_client()
        try:
            logger.info(f"Attempting login for user: {login_data.email}")
            
            # Sign in user with Supabase
            res = client.auth.sign_in_with_password({
                "email": login_data.email,
                "password": login_data.password
            })

            if res.session and res.user:
                logger.info(f"Successfully logged in user: {res.user.id} ({res.user.email})")

                # Map Supabase response to our models
                token_data = TokenData(
                    access_token=res.session.access_token,
                    refresh_token=res.session.refresh_token or "",  # Ensure refresh token exists
                    token_type="bearer",
                    expires_in=res.session.expires_in or 3600,  # Default to 1 hour if missing
                )
                
                # Extract user metadata
                metadata = res.user.user_metadata or {}
                
                # Map Supabase user to UserRead model
                user_read = UserRead(
                    id=str(res.user.id),
                    email=res.user.email,
                    roles=["authenticated"],  # Default role
                    full_name=metadata.get("full_name"),
                    avatar_url=metadata.get("avatar_url"),
                )

                return AuthResponse(session=token_data, user=user_read)
            else:
                logger.error(f"Supabase login response missing session or user data for {login_data.email}. Response: {res}")
                raise AuthServiceError("Login failed due to an unexpected Supabase response.", 500)

        except Exception as e:
            logger.error(f"Error during user login: {e}", exc_info=True)
            
            # Handle specific error cases
            error_message = str(e).lower()
            if "invalid login" in error_message or "invalid email" in error_message or "invalid password" in error_message:
                raise AuthServiceError("Invalid email or password.", 401)  # 401 Unauthorized
            
            # Generic error case
            raise AuthServiceError(f"Login failed: {str(e)}", 500) 