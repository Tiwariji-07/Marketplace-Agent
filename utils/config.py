import os
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Settings(BaseSettings):
    # Application Settings
    APP_NAME: str = "Multi-Agent AI Assistant"
    DEBUG: bool = os.getenv("DEBUG", "False").lower() in ("true", "1", "t")
    
    # OpenAI Configuration
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4-1106-preview")
    
    # Redis Configuration
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379")
    REDIS_PASSWORD: str = os.getenv("REDIS_PASSWORD", "")
    REDIS_DB: int = int(os.getenv("REDIS_DB", 0))
    
    # GitHub API Configuration
    GITHUB_TOKEN: str = os.getenv("GITHUB_TOKEN", "")
    
    # API Settings
    API_PREFIX: str = "/api/v1"
    API_BASE_URL: str = os.getenv("API_BASE_URL", "http://localhost:8000/api/v1")
    CORS_ORIGINS: list = ["*"]
    
    # Session Settings
    SESSION_EXPIRE_SECONDS: int = 86400  # 24 hours
    
    # Frontend Configuration
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:8501")
    
    # Logging Configuration
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    # Rate Limiting
    RATE_LIMIT: int = int(os.getenv("RATE_LIMIT", "100"))  # requests per minute
    RATE_LIMIT_WINDOW: int = int(os.getenv("RATE_LIMIT_WINDOW", "60"))  # seconds
    
    class Config:
        env_file = ".env"
        case_sensitive = True

# Create settings instance
settings = Settings()

# Validate required settings
if not settings.OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY environment variable is required")

# Configure Redis URL with password if provided
if settings.REDIS_PASSWORD and "@" not in settings.REDIS_URL:
    # Insert password into Redis URL
    redis_parts = settings.REDIS_URL.split("://")
    if len(redis_parts) == 2:
        settings.REDIS_URL = f"{redis_parts[0]}://:{settings.REDIS_PASSWORD}@{redis_parts[1]}"
