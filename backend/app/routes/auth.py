from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.repos import auth_repo
from app.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    GoogleLoginRequest,
    AuthResponse,
    UserResponse,
)
from app.utils.auth.jwt import create_access_token, get_current_user
from app.models.user import User

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/login",
             response_model=AuthResponse,
             status_code=status.HTTP_200_OK,
             summary="Login with email and password",
             response_description="User data and JWT token")
async def login(
    data: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Authenticate user with email and password. \\
    Returns user data and a JWT access token.
    """
    user = await auth_repo.authenticate_user(db, data.email, data.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Nieprawidłowy email lub hasło",
        )
    token = create_access_token(user.id)
    return AuthResponse(user=UserResponse.from_db(user), token=token)


@router.post("/register",
             response_model=AuthResponse,
             status_code=status.HTTP_201_CREATED,
             summary="Register a new user",
             response_description="New user data and JWT token")
async def register(
    data: RegisterRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Register a new user with email and password. \\
    Returns user data and a JWT access token.
    """
    existing = await auth_repo.get_user_by_email(db, data.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Użytkownik z tym adresem email już istnieje",
        )
    user = await auth_repo.register_user(db, data.firstName, data.lastName, data.email, data.password)
    token = create_access_token(user.id)
    return AuthResponse(user=UserResponse.from_db(user), token=token)


@router.post("/google",
             response_model=AuthResponse,
             status_code=status.HTTP_200_OK,
             summary="Login or register with Google",
             response_description="User data and JWT token")
async def google_login(
    data: GoogleLoginRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Login or register using Google OAuth credential. \\
    Creates a new user if one doesn't exist.
    """
    # In production: verify Google token via Google API
    # For now, create/get a stub google user
    user = await auth_repo.get_or_create_google_user(
        db,
        google_id=data.credential,
        email=f"{data.credential}@google.oauth",
        name="Google",
        surname="User",
    )
    token = create_access_token(user.id)
    return AuthResponse(user=UserResponse.from_db(user), token=token)


@router.get("/current",
            response_model=UserResponse,
            status_code=status.HTTP_200_OK,
            summary="Get current authenticated user",
            response_description="Current user data")
async def get_me(
    current_user: User = Depends(get_current_user),
):
    """
    Returns data of the currently authenticated user.
    """
    return UserResponse.from_db(current_user)


@router.post("/logout",
             status_code=status.HTTP_200_OK,
             summary="Logout",
             response_description="Logout confirmation")
async def logout():
    """
    Logout the current user. \\
    Client should remove the token from storage.
    """
    return {"message": "Wylogowano"}
