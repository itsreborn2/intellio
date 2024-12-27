"""보안 관련 유틸리티 함수들"""

from datetime import datetime, timedelta
from typing import Any, Union

from passlib.context import CryptContext
from jose import jwt

# 비밀번호 해싱을 위한 설정
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT 설정
SECRET_KEY = "your-secret-key-here"  # TODO: 환경 변수로 이동
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """평문 비밀번호와 해시된 비밀번호를 비교

    Args:
        plain_password (str): 평문 비밀번호
        hashed_password (str): 해시된 비밀번호

    Returns:
        bool: 비밀번호 일치 여부
    """
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """비밀번호를 해시화

    Args:
        password (str): 평문 비밀번호

    Returns:
        str: 해시된 비밀번호
    """
    return pwd_context.hash(password)


def create_access_token(
    subject: Union[str, Any], expires_delta: timedelta = None
) -> str:
    """JWT 액세스 토큰 생성

    Args:
        subject: 토큰에 포함될 주체 (보통 user_id)
        expires_delta: 만료 시간

    Returns:
        str: JWT 토큰
    """
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode = {"exp": expire, "sub": str(subject)}
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt
