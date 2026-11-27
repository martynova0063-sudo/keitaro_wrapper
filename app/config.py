from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    keitaro_base_url: str = "https://keitaro-for-tests.etolegko.com/admin_api/v1"
    keitaro_api_key: str = ""

    database_url: str = "sqlite:///./keitaro_wrapper.db"

    # Значения по умолчанию для стенда; если в /domains, /groups, /traffic_sources
    # найдётся сущность с названием FORTESTS, возьмём её id из API.
    default_domain_id: int = 1813
    default_group_id: int = 10332
    default_traffic_source_id: int = 836

    google_url: str = "https://google.com"
    campaign_name_prefix: str = "test_"


@lru_cache
def get_settings() -> Settings:
    return Settings()
