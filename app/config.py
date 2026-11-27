from functools import lru_cache
from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator

load_dotenv()

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')
    environment: str = 'local'
    database_url: str = 'sqlite+aiosqlite:///./cohire.db'
    identity_database_url: str = 'sqlite+aiosqlite:///./identity.db'
    agent_mode: str = 'demo'
    dev_auth: bool = False
    dev_token: str = ''
    tenant_id: str = '11111111-1111-4111-8111-111111111111'
    identity_key: str = ''
    oidc_issuer: str = ''
    oidc_audience: str = ''
    oidc_jwks_url: str = ''
    gemini_parse_model: str = ''
    gemini_match_model: str = ''
    agent_transport: str = 'local'
    a2a_url: str = 'http://127.0.0.1:8001'
    a2a_token: str = ''
    max_run_seconds: int = 120
    max_candidates: int = 50
    max_attempts: int = 3
    pubsub_topic: str = ''
    pubsub_audience: str = ''
    pubsub_service_account: str = ''
    outreach_mode: str = 'draft'
    @model_validator(mode='after')
    def guard(self):
        if self.environment != 'local':
            # This release is intentionally gated until the production checklist is met.
            raise ValueError('Production activation requires the documented release gates; this build is local/integration only')
        if self.dev_auth and len(self.dev_token) < 24:
            raise ValueError('DEV_TOKEN must be at least 24 characters')
        if self.outreach_mode != 'draft':
            raise ValueError('This release supports draft outreach only')
        if self.agent_mode not in ('demo', 'gemini'):
            raise ValueError('Unknown agent mode')
        return self

@lru_cache
def settings():
    return Settings()
