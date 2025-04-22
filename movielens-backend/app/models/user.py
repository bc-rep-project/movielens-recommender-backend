# backend/app/models/user.py

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, EmailStr

# --- Base Model ---
class UserBase(BaseModel):
    """Basic user profile information, often derived from JWT or Supabase metadata."""
    email: Optional[EmailStr] = Field(None, description="User's email address.")
    # Fields from Supabase user_metadata
    full_name: Optional[str] = Field(None, description="User's full name.")
    avatar_url: Optional[str] = Field(None, description="URL to user's avatar image.")
    # Add other custom fields from user_metadata if needed

# --- Model for API Responses ---
class UserRead(UserBase):
    """Model representing user information returned by the API (e.g., GET /api/users/me)."""
    id: str = Field(..., description="User's unique identifier (from Supabase Auth JWT 'sub' claim).")
    # Fields from Supabase app_metadata or JWT claims
    roles: List[str] = Field(default_factory=list, description="Roles assigned to the user (e.g., 'authenticated').")
    # You could include the raw app_metadata or user_metadata if needed by the frontend
    # app_metadata: Dict[str, Any] = Field(default_factory=dict)
    # user_metadata: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        from_attributes = True

# --- Model for Internal Use (Optional) ---
# You might have a UserInDB model if you store/sync user profiles
# separate from Supabase Auth, but for this project, UserRead might suffice.
# class UserInDB(UserRead):
#     hashed_password: Optional[str] = None # Example if managing passwords yourself (NOT recommended with Supabase)
#     is_active: bool = True