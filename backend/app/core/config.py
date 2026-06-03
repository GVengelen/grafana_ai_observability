from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "pokemon-qa-api"
    app_env: str = "development"
    app_debug: bool = True

    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/pokemon_qa"

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-haiku-4-5-20251001"
    anthropic_timeout_seconds: int = 20

    pokeapi_base_url: str = "https://pokeapi.co/api/v2"

    api_prefix: str = "/api/v1"

    # Sigil AI observability
    sigil_enabled: bool = True
    sigil_endpoint: str = ""
    sigil_auth_tenant_id: str = ""
    sigil_auth_token: str = ""
    otel_service_name: str = "pokemon-qa-api"

    # OpenLIT observability
    openlit_enabled: bool = True
    openlit_otlp_endpoint: str = "http://localhost:4318"


settings = Settings()
