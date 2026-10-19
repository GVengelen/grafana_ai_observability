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

    # Agent Observability guards (preflight hooks). The SDK has no env vars for these.
    # Production can set AGENTO11Y_GUARDS_FAIL_OPEN=false (strict mode: block when the guard is unreachable).
    agento11y_guards_enabled: bool = True
    agento11y_guards_fail_open: bool = True
    agento11y_guards_timeout_ms: int = 5000

    # OpenTelemetry
    otel_enabled: bool = True
    otel_service_name: str = "pokemon-qa-api"


settings = Settings()
