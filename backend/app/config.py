from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://bidwatch:bidwatch_dev@localhost:5432/bidwatch"
    DATABASE_URL_SYNC: str = "postgresql+psycopg2://bidwatch:bidwatch_dev@localhost:5432/bidwatch"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # JWT
    JWT_SECRET: str = "change-this-to-a-random-secret-key"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # bid-collectors
    DATA_GO_KR_KEY: str = ""
    BIZINFO_API_KEY: str = ""

    # Claude AI
    ANTHROPIC_API_KEY: str = ""

    # Toss Payments
    TOSS_SECRET_KEY: str = ""

    # Email
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
