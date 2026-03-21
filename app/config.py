from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    DATABASE_HOST: str
    DATABASE_PORT: int = 5432
    DATABASE_NAME: str
    DATABASE_USER: str
    DATABASE_PASSWORD: str
    DATABASE_URL: str | None = None

    DATABASE_POOL_SIZE: int = 5
    DATABASE_MAX_OVERFLOW: int = 10
    DATABASE_POOL_TIMEOUT: int = 30

    SUPABASE_URL: str
    """Project URL, e.g. https://<ref>.supabase.co"""

    SUPABASE_ANON_KEY: str | None = None
    """Required to fetch JWKS from /auth/v1/keys (Supabase requires apikey header)."""

    SUPABASE_JWT_AUDIENCE: str = "authenticated"
    SUPABASE_JWT_SECRET: str | None = None
    """JWT secret from Supabase dashboard; used when tokens are signed with HS256."""

    @property
    def supabase_jwt_issuer(self) -> str:
        return f"{self.SUPABASE_URL.rstrip('/')}/auth/v1"

    @property
    def async_database_url(self) -> str:
        if self.DATABASE_URL:
            url = self.DATABASE_URL
            if url.startswith("postgresql://"):
                return url.replace("postgresql://", "postgresql+asyncpg://", 1)
            return url
        return (
            f"postgresql+asyncpg://{self.DATABASE_USER}:{self.DATABASE_PASSWORD}"
            f"@{self.DATABASE_HOST}:{self.DATABASE_PORT}/{self.DATABASE_NAME}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
