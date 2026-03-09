from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from os import path

PROJECT_PATH = path.realpath(path.join(path.dirname(__file__), "../.."))


class CommonSettings(BaseSettings):
    APP_NAME: str = Field(default="neurosaber-backend")
    DEBUG_MODE: bool = Field(default=False)

    HUMAN_READABLE_LOGGING: bool = Field(default=True)
    LOG_LEVEL: str = Field(default="INFO")


class DatabaseSettings(BaseSettings):
    DB_URL: str
    DB_USE_NULLPOOL: bool = Field(default=True)
    DB_POOL_SIZE: int = Field(default=5)
    DB_POOL_PRE_PING: bool = Field(default=True)
    POOL_RECYCLE_MINUTES: int = Field(default=5)
    DB_STATEMENT_TIMEOUT_MS: int = Field(default=10000)
    DB_MAX_OVERFLOW: int = Field(default=10)
    REPOSITORY_NAME: str = Field(default="SQL")


class CredentialsSettings(BaseSettings):
    AUTH_JWT_SECRET: str = ""


class MLSettings(BaseSettings):
    ML_APP_ID: str = ""
    ML_CLIENT_SECRET: str = ""
    ML_REDIRECT_URI: str = Field(
        default="http://localhost:8000/auth/ml/callback")
    ML_FREE_SHIPPING_LIMIT: int = 32990
    ML_AUTH_STATE_EXPIRY_MINUTES: int = Field(
        default=10, description="OAuth state expiry in minutes")
    ML_TOKEN_EXPIRY_BUFFER_SECONDS: int = Field(
        default=300, description="Buffer time before token expiry to refresh")


class FrontendSettings(BaseSettings):
    FRONTEND_URL: str = Field(default="http://localhost:3000")


class AWSConfig(BaseSettings):
    ASSETS_BUCKET: str = "ml-app-assets"
    REGION_NAME: str = "us-east-1"
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    ENDPOINT_URL: str | None = None


class EnvironmentSettings(BaseSettings):
    ENVIRONMENT: str = Field(default="local")


class GuruSettings(BaseSettings):
    GURU_API_URL: str = Field(default="https://digitalmanager.guru/api/v2")
    GURU_API_KEY: str = ""
    GURU_INGRESSO_GROUP_ID: str = ""
    GURU_SYNC_INTERVAL_MINUTES: int = Field(default=60)


class AdminSettings(BaseSettings):
    ADMIN_API_KEY: str = ""


class Settings(CommonSettings,
               DatabaseSettings,
               MLSettings,
               CredentialsSettings,
               FrontendSettings,
               AWSConfig,
               EnvironmentSettings,
               GuruSettings,
               AdminSettings):
    """
    Settings for the application.
    """
    model_config = SettingsConfigDict(env_file=path.join(PROJECT_PATH, '.env'))


settings = Settings()
