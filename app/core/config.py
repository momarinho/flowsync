from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "FlowSync Data Ingestion & Integration Engine"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    # PostgreSQL Database URL
    DATABASE_URL: str = "postgresql+psycopg2://flowsync_user:flowsync_pass@localhost:5432/flowsync_db"
    
    # Webhook HMAC Secret
    WEBHOOK_SECRET: str = "flowls_secret_hmac_key_2026"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

settings = Settings()
