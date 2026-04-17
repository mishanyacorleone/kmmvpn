from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext

from config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer_scheme = HTTPBearer()

ALGORITHM = "HS256"


def create_access_token() -> str:
    """Создаёт JWT токен для админа"""
    expire = datetime.now(timezone.utc) + timedelta(hours=settings.admin_jwt_ttl_hours)
    payload = {
        "sub": "admin",
        "exp": expire,
        "iat": datetime.now(timezone.utc)
    }
    return jwt.encode(payload, settings.admin_jwt_secret, algorithm=ALGORITHM)


def verify_password(plain_password: str) -> bool:
    """Проверяет пароль админа"""
    return plain_password == settings.admin_password


def verify_token(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)) -> str:
    """
    Dependency для защищенных эндпоинтов.
    
    Проверяет JWT токен из заголовка Authorization: Bearer <token>.
    """
    token = credentials.credentials
    try:
        payload = jwt.decode(token, settings.admin_jwt_secret, algorithms=[ALGORITHM])
        subject: str = payload.get("sub")
        if subject != "admin":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Невалидный токен")
        return subject
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Токен истёк или невалиден",
            headers={"WWW-Authenticate": "Bearer"}
        )
