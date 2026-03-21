import time
import uuid
from collections.abc import AsyncGenerator

import requests
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwk, jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db as get_db_session
from app.services import user_service

security = HTTPBearer(auto_error=False)

JWKS_CACHE_TTL_SEC = 600
_jwks_cache: dict | None = None
_jwks_fetched_at: float = 0.0


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async for session in get_db_session():
        yield session


def _fetch_jwks() -> dict:
    settings = get_settings()
    url = f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/keys"
    headers: dict[str, str] = {}
    if settings.SUPABASE_ANON_KEY:
        headers["apikey"] = settings.SUPABASE_ANON_KEY
    response = requests.get(url, headers=headers, timeout=15)
    if response.status_code == 401:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Supabase rejected JWKS request; set SUPABASE_ANON_KEY "
                "(apikey header required for /auth/v1/keys)"
            ),
        )
    if response.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not fetch signing keys from Supabase",
        )
    return response.json()


def _get_jwks() -> dict:
    global _jwks_cache, _jwks_fetched_at
    now = time.time()
    if _jwks_cache is not None and now - _jwks_fetched_at < JWKS_CACHE_TTL_SEC:
        return _jwks_cache
    _jwks_cache = _fetch_jwks()
    _jwks_fetched_at = now
    return _jwks_cache


def _decode_rs256(token: str) -> dict:
    settings = get_settings()
    jwks = _get_jwks()
    header = jwt.get_unverified_header(token)
    kid = header.get("kid")
    keys = jwks.get("keys") or []
    rsa_key = None
    for key in keys:
        if kid and key.get("kid") == kid:
            rsa_key = jwk.construct(key)
            break
    if rsa_key is None and len(keys) == 1:
        rsa_key = jwk.construct(keys[0])
    if rsa_key is None:
        raise JWTError("No matching JWK for token")

    return jwt.decode(
        token,
        rsa_key,
        algorithms=["RS256"],
        audience=settings.SUPABASE_JWT_AUDIENCE,
        issuer=settings.supabase_jwt_issuer,
        options={"leeway": 10},
    )


def _decode_hs256(token: str) -> dict:
    settings = get_settings()
    if not settings.SUPABASE_JWT_SECRET:
        raise JWTError("JWT secret not configured")
    return jwt.decode(
        token,
        settings.SUPABASE_JWT_SECRET,
        algorithms=["HS256"],
        audience=settings.SUPABASE_JWT_AUDIENCE,
        issuer=settings.supabase_jwt_issuer,
        options={"leeway": 10},
    )


def decode_supabase_jwt(token: str) -> dict:
    header = jwt.get_unverified_header(token)
    alg = header.get("alg", "RS256")
    if alg == "HS256":
        return _decode_hs256(token)
    return _decode_rs256(token)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> dict:
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        return decode_supabase_jwt(credentials.credentials)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user_id(
    db: AsyncSession = Depends(get_db),
    payload: dict = Depends(get_current_user),
) -> uuid.UUID:
    sub = payload.get("sub")
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token: missing sub",
        )
    try:
        user_id = uuid.UUID(str(sub))
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token: bad sub",
        )
    await user_service.ensure_user(db, user_id, payload.get("email"))
    return user_id
