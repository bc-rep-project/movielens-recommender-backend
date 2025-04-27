from typing import Optional, Dict, Any, List
from pydantic import BaseModel, EmailStr, Field

class UserRead(BaseModel):
    """User data returned in responses"""
    id: str
    email: EmailStr
    roles: Optional[List[str]] = ["authenticated"]
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None

class UserCreate(BaseModel):
    """Data required to register a new user"""
    email: EmailStr
    password: str = Field(..., min_length=6, description="User password (min 6 characters)")
    # Add any other required fields for signup
    full_name: Optional[str] = None

class UserLogin(BaseModel):
    """Data required for user login"""
    email: EmailStr
    password: str

class TokenData(BaseModel):
    """Represents the core token information from Supabase"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int

class AuthResponse(BaseModel):
    """Response containing token data and user info after successful login"""
    session: TokenData
    user: UserRead

class RegisterResponse(BaseModel):
    """Response after successful registration"""
    message: str = "Registration successful. Please check your email for verification."
    user_id: str
    email: EmailStr 