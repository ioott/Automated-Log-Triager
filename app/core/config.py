from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """
    Global application settings.
    Strictly uses environment variables. No hardcoded credentials.
    """
    PROJECT_NAME: str = "Automated Log Triager & Diagnostic Agent"
    VERSION: str = "0.1.0"
    ENVIRONMENT: str = "development"
    
    # AI Settings (Phase 3 - Google Gemini)
    GOOGLE_API_KEY: str = "placeholder-key"
    GEMINI_MODEL_NAME: str = "gemini-2.5-flash"
    
    # Vector DB Settings (Phase 2)
    VECTOR_DB_URL: str = "http://chromadb:8000"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()
