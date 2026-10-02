"""Application settings loaded from environment variables / .env file."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="PX_")

    ncbi_api_key: str | None = None
    ncbi_email: str  # NCBI requires a contact email for E-utilities
    ncbi_tool: str = "pubmed-extraction"

    anthropic_api_key: str
    extraction_model: str = "claude-sonnet-5"
    extraction_max_tokens: int = 8192
    classification_model: str = "claude-haiku-4-5-20251001"
    classification_max_tokens: int = 1024

    @property
    def ncbi_rate_limit(self) -> float:
        """Max requests per second allowed by NCBI (10 with key, 3 without)."""
        return 10.0 if self.ncbi_api_key else 3.0


settings = Settings()
