from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    FRONTEND_ORIGINS: str = "http://localhost:5173"
    
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

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
