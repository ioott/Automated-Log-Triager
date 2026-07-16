from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Global application settings.
    Strictly uses environment variables. No hardcoded credentials.
    """
    PROJECT_NAME: str = "Automated Log Triager & Diagnostic Agent"
    VERSION: str = "0.2.0"
    ENVIRONMENT: str = "development"

    # AI Settings (Phase 3 - Google Gemini)
    GOOGLE_API_KEY: str = "placeholder-key"
    GEMINI_MODEL_NAME: str = "gemini-2.5-flash"

    # Vector DB Settings - Chroma Cloud (managed, replaces the old
    # self-hosted ChromaDB-on-Render setup). No default: these are secrets
    # that must come from the environment, not a placeholder that could
    # silently point at nothing.
    CHROMA_API_KEY: str = "placeholder-key"
    CHROMA_TENANT: str = "placeholder-tenant"
    CHROMA_DATABASE: str = "log-triager"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
