from fastapi import HTTPException, status

import bcrypt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.schemas.auth import RegisterRequest, AuthResponse, UserResponse
from app.utils.auth.jwt import create_access_token


def hash_password(password: str) -> str:
    pwd_bytes = password.encode("utf-8")[:72]
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    pwd_bytes = plain_password.encode("utf-8")[:72]
    return bcrypt.checkpw(pwd_bytes, hashed_password.encode("utf-8"))


async def register_user(
        db: AsyncSession,
        data: RegisterRequest
) -> AuthResponse:
    existing = await get_user_by_email(db, data.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Użytkownik z tym adresem email już istnieje",
        )
    hashed = hash_password(data.password)
    user = User(
        name=data.firstName,
        surname=data.lastName,
        email=data.email,
        hashed_password=hashed,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    token = create_access_token(user.id)
    return AuthResponse(user=UserResponse.from_db(user), token=token)


async def authenticate_user(db: AsyncSession, email: str, password: str) -> User | None:
    stmt = select(User).where(User.email == email)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None or user.hashed_password is None:
        return None

    if not verify_password(password, user.hashed_password):
        return None

    return user


async def get_or_create_google_user(
    db: AsyncSession, google_id: str, email: str, name: str, surname: str
) -> User:
    stmt = select(User).where(User.google_id == google_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user is not None:
        return user

    # Check if user exists by email
    stmt = select(User).where(User.email == email)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user is not None:
        user.google_id = google_id
        await db.commit()
        await db.refresh(user)
        return user

    # Create new user
    user = User(
        name=name,
        surname=surname,
        email=email,
        google_id=google_id,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def get_user_by_id(db: AsyncSession, user_id: int) -> User | None:
    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    stmt = select(User).where(User.email == email)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()
