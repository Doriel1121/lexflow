from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # Primary DB URL (prefer this)
    DATABASE_URL: str = ""
    # Render-provided URLs (optional; used if DATABASE_URL is empty)
    RENDER_INTERNAL_DATABASE_URL: str | None = None
    RENDER_EXTERNAL_DATABASE_URL: str | None = None
    # Render-provided components (optional)
    RENDER_DB_HOST: str | None = None
    RENDER_DB_PORT: int | None = None
    RENDER_DB_USER: str | None = None
    RENDER_DB_PASSWORD: str | None = None
    RENDER_DB_NAME: str | None = None
    # Component parts fallback (optional)
    DB_HOST: str | None = None
    DB_PORT: int | None = None
    DB_USER: str | None = None
    DB_PASSWORD: str | None = None
    DB_NAME: str | None = None
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 14  # 14 days
    FRONTEND_ORIGINS: str = "http://localhost:5173"
    ENVIRONMENT: str = "development"  # "development", "staging", "production"
    # Back-compat env var
    APP_ENV: str | None = None
    
    # OAuth
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    MICROSOFT_CLIENT_ID: str = ""
    MICROSOFT_CLIENT_SECRET: str = ""

    # Risk APIs
    OPENSANCTIONS_API_KEY: str = ""

    # Document processing flow control
    # "auto" = choose based on file size, "celery" = always queue Celery, "background" = always BackgroundTask
    DOCUMENT_PROCESSING_MODE: str = "auto"
    # If mode="auto", files >= this size (MB) use Celery, otherwise BackgroundTask
    DOCUMENT_PROCESSING_CELERY_MIN_MB: int = 10
    # Hard cutoff for total processing time (seconds). When exceeded, finish without AI.
    DOCUMENT_MAX_PROCESSING_SECONDS: int = 3600

    # AI tag filtering
    AI_TAG_MIN_CONFIDENCE: float = 0.55
    AI_TAG_MAX_PER_DOCUMENT: int = 8

    # Embedding fan-out (Celery only)
    DOCUMENT_EMBEDDING_FANOUT: bool = True

    # AI analysis timeout (seconds)
    AI_ANALYSIS_TIMEOUT_SECONDS: int = 120

    # Reaper: mark stuck docs as completed_without_ai after this many minutes
    DOCUMENT_STUCK_MINUTES: int = 30

    # Auth hardening
    PASSWORD_MIN_LENGTH: int = 10
    RATE_LIMIT_LOGIN_PER_MINUTE: int = 20

    # Cloudflare R2 Storage
    R2_ENABLED: bool = False  # Set to True to use R2; False to use local storage
    R2_ACCOUNT_ID: str = ""
    R2_ACCESS_KEY_ID: str = ""
    R2_SECRET_ACCESS_KEY: str = ""
    R2_BUCKET_NAME: str = ""
    R2_ENDPOINT_URL: str = ""  # e.g., https://[account-id].r2.cloudflarestorage.com
    R2_PUBLIC_URL: str = ""    # e.g., https://[bucket-name].yourdomain.com or use Render proxy URL

    # Backblaze B2 Storage
    B2_ENABLED: bool = False  # Set to True to use B2; False to use local storage
    B2_BUCKET_NAME: str = ""
    B2_APPLICATION_KEY_ID: str = ""  # Looks like: 00000xxxxxxxxxxxxxxx
    B2_APPLICATION_KEY: str = ""     # Looks like: K00xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
    B2_ENDPOINT_URL: str = ""  # e.g., https://s3.us-west-000.backblazeb2.com
    B2_PUBLIC_URL: str = ""    # e.g., https://your-custom-domain or leave empty for default B2 URLs

    # Single source of truth: repo root .env
    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parents[3] / ".env"),
        extra="ignore",
    )

    def model_post_init(self, __context) -> None:
        # Backwards compatibility: honor APP_ENV if ENVIRONMENT wasn't explicitly set
        if self.ENVIRONMENT == "development" and self.APP_ENV:
            self.ENVIRONMENT = self.APP_ENV

        # Prefer explicit DATABASE_URL, otherwise fall back to Render URLs, then components.
        if self.DATABASE_URL:
            return

        candidate = self.RENDER_INTERNAL_DATABASE_URL or self.RENDER_EXTERNAL_DATABASE_URL
        if candidate:
            self.DATABASE_URL = candidate
            return

        host = self.DB_HOST or self.RENDER_DB_HOST
        user = self.DB_USER or self.RENDER_DB_USER
        password = self.DB_PASSWORD or self.RENDER_DB_PASSWORD
        name = self.DB_NAME or self.RENDER_DB_NAME
        port = self.DB_PORT or self.RENDER_DB_PORT or 5432

        if host and user and password and name:
            self.DATABASE_URL = (
                f"postgresql+asyncpg://{user}:{password}"
                f"@{host}:{port}/{name}"
            )
            return

        raise ValueError(
            "DATABASE_URL is required. Set DATABASE_URL or "
            "RENDER_INTERNAL_DATABASE_URL/RENDER_EXTERNAL_DATABASE_URL or "
            "DB_HOST/DB_PORT/DB_USER/DB_PASSWORD/DB_NAME or "
            "RENDER_DB_HOST/RENDER_DB_PORT/RENDER_DB_USER/RENDER_DB_PASSWORD/RENDER_DB_NAME."
        )

settings = Settings()
