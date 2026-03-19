from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "用户管理系统 API"
    APP_VERSION: str = "1.0.0"
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    DATABASE_URL: str = "sqlite:///./user_management.db"
    
    class Config:
        env_file = ".env"


settings = Settings()
