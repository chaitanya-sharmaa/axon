from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator
import os

os.environ["AXON_ALLOWED_DOMAINS"] = "a,b,c"

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AXON_")
    allowed_domains: str | list[str] = Field(default_factory=list)

    @field_validator('allowed_domains', mode='before')
    @classmethod
    def split_str(cls, v):
        if isinstance(v, str):
            return [x.strip() for x in v.split(',')]
        return v

settings = Settings()
print(settings.allowed_domains)
