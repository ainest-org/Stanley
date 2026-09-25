from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # App
    app_env: str = "development"
    app_secret_key: str = "change-me-in-env"
    frontend_base_url: str = "http://localhost:3000"
    backend_base_url: str = "http://localhost:8000"

    # Database
    database_url: str = "postgresql+asyncpg://pmtool:pmtool@localhost:5432/pmtool"

    # Redis / Huey
    redis_url: str = "redis://localhost:6379/0"

    # GitLab OAuth2 (self-hosted instance, per PRD Section 5.1 / 18)
    gitlab_instance_url: str = "https://gitlab.example.com"
    gitlab_oauth_client_id: str = ""
    gitlab_oauth_client_secret: str = ""
    gitlab_oauth_redirect_uri: str = "http://localhost:8000/api/auth/callback"
    gitlab_oauth_scopes: str = "read_api read_user"

    # Org-wide service account token used by the sync engine's background jobs (webhook
    # processing, reconciliation) — never a per-user token, per NFR Section 14.
    gitlab_sync_service_token: str = ""

    # Token encryption (Fernet key, base64-encoded 32 bytes) — PRD 14: OAuth tokens encrypted at rest
    token_encryption_key: str = ""

    # Session / JWT
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24 * 7


@lru_cache
def get_settings() -> Settings:
    return Settings()
