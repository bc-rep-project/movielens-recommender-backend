import logging
from fastapi import APIRouter, Depends, HTTPException, status

from app.models.auth import UserCreate, UserLogin, AuthResponse, RegisterResponse
from app.services.auth_service import AuthService, AuthServiceError
from app.services.pipeline_trigger_service import PipelineTriggerService

logger = logging.getLogger(__name__)
router = APIRouter()

# --- Dependencies ---
def get_auth_service() -> AuthService:
    return AuthService()

def get_pipeline_trigger_service() -> PipelineTriggerService:
    return PipelineTriggerService()

@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register New User",
    description="Registers a new user account and triggers the initial data pipeline check asynchronously.",
    responses={
        409: {"description": "User with this email already exists"},
        400: {"description": "Invalid input data"},
        500: {"description": "Internal server error during registration"},
    }
)
async def register_user(
    user_in: UserCreate,
    auth_service: AuthService = Depends(get_auth_service),
    trigger_service: PipelineTriggerService = Depends(get_pipeline_trigger_service)
):
    """
    Handles user registration. On first successful registration (handled by Supabase),
    it asynchronously triggers a check to run the initial data processing pipeline.
    """
    try:
        registered_user = await auth_service.register_user(user_in)

        # After successful registration, trigger the pipeline check
        # This publish is fire-and-forget from the API's perspective
        await trigger_service.trigger_pipeline_if_needed(
            user_id=registered_user.user_id,
            email=registered_user.email
        )
        # Even if triggering fails, registration was successful, so return 201
        return registered_user

    except AuthServiceError as e:
        logger.warning(f"Registration failed: {e.message} (Status Code: {e.status_code})")
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        logger.error(f"Unexpected error during /register endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An internal error occurred.")


@router.post(
    "/login",
    response_model=AuthResponse,
    summary="User Login",
    description="Authenticates a user with email and password, returning JWT tokens and user info.",
    responses={
        401: {"description": "Invalid email or password"},
        400: {"description": "Invalid input data"},
        500: {"description": "Internal server error during login"},
    }
)
async def login_user(
    login_data: UserLogin,
    auth_service: AuthService = Depends(get_auth_service),
):
    """
    Handles user login using email and password.
    """
    try:
        auth_response = await auth_service.login_user(login_data)
        return auth_response
    except AuthServiceError as e:
        logger.warning(f"Login failed: {e.message} (Status Code: {e.status_code})")
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        logger.error(f"Unexpected error during /login endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An internal error occurred.") 