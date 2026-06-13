from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    APP_NAME: str = "连锁门店经营数据分析平台"
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/store_analytics"
    DATABASE_URL_SYNC: str = "postgresql://postgres:postgres@localhost:5432/store_analytics"
    SECRET_KEY: str = "change-this-in-production-use-openssl-rand-hex-32"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480
    UPLOAD_DIR: str = "./uploads"
    REPORT_DIR: str = "./reports"
    CHUNK_SIZE: int = 10000
    MAX_UPLOAD_SIZE: int = 200 * 1024 * 1024

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
