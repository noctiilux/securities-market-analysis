from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db_session, get_user_by_id
from models import User

JWT_SECRET = os.getenv("JWT_SECRET", "change_me_in_production")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "120"))

# Используем pbkdf2_sha256 как основной алгоритм:
# он стабилен в Docker и не зависит от нативного bcrypt-бэкенда.
# bcrypt оставляем для обратной совместимости со старыми хешами (если есть).
pwd_context = CryptContext(schemes=["pbkdf2_sha256", "bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def hash_password(password: str) -> str:
    """Хеширует пароль пользователя."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    """Проверяет пароль пользователя."""
    return pwd_context.verify(plain_password, password_hash)


def create_access_token(user_id: int) -> str:
    """Создает JWT access token с user_id в subject."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": str(user_id), "exp": expire}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    session: AsyncSession = Depends(get_db_session),
) -> User:
    """Извлекает текущего пользователя из JWT токена."""
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Не удалось проверить учетные данные",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        sub = payload.get("sub")
        if sub is None:
            raise credentials_error
        user_id = int(sub)
    except (JWTError, ValueError) as exc:
        raise credentials_error from exc

    user = await get_user_by_id(session, user_id)
    if not user:
        raise credentials_error

    return user


# Пример использования:
# token = create_access_token(user_id=1)
